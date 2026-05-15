use vstd::prelude::*;
use vstd::simple_pptr::*;

fn main() {}

verus!{

pub type CpuId = usize;

pub type PagePtr = usize;

pub type VAddr = usize;

pub type PAddr = usize;

pub type PageMapPtr = usize;

pub type Pcid = usize;

pub type IOid = usize;

pub type L4Index = usize;

pub type L3Index = usize;

pub type L2Index = usize;

pub type L1Index = usize;

// File: pagetable/pagemap.rs
pub struct PageMap {
    pub ar: Array<usize, 512>,
    pub spec_seq: Ghost<Seq<PageEntry>>,  // pub level: Ghost<usize>,
    // not used for now.
}

impl PageMap {

    pub open spec fn wf(&self) -> bool {
        &&& self.ar.wf()
        &&& self.spec_seq@.len() == 512
        &&& forall|i: int|
            #![trigger usize2page_entry(self.ar@[i])]
            0 <= i < 512 ==> (usize2page_entry(self.ar@[i])
                =~= self.spec_seq@[i])
            // &&&
            // forall|i:int|
            //     #![trigger usize2page_entry(self.ar@[i]).is_empty()]
            //     0<=i<512 ==> (usize2page_entry(self.ar@[i]).is_empty() <==> self.ar@[i] == 0)

    }

    pub open spec fn spec_index(&self, index: usize) -> PageEntry
        recommends
            0 <= index < 512,
    {
        self.spec_seq@[index as int]
    }

}



// File: pagetable/entry.rs
#[derive(Clone,Debug)]
pub struct PageEntryPerm {
    pub present: bool,
    pub ps: bool,
    pub write: bool,
    pub execute_disable: bool,
    pub user: bool,
}

#[derive(Clone,Debug)]
pub struct PageEntry {
    pub addr: PAddr,
    pub perm: PageEntryPerm,
    // pub ps: bool,
}

impl PageEntry {

    pub open spec fn is_empty(&self) -> bool {
        &&& self.addr == 0
        &&& self.perm.present == false
        &&& self.perm.ps == false
        &&& self.perm.write == false
        &&& self.perm.execute_disable == false
        &&& self.perm.user == false
    }

}


pub struct MapEntry {
    pub addr: PAddr,
    pub write: bool,
    pub execute_disable: bool,
}

pub open spec fn usize2present(v: usize) -> bool {
    (v & PAGE_ENTRY_PRESENT_MASK as usize) != 0
}

pub open spec fn usize2ps(v: usize) -> bool {
    (v & PAGE_ENTRY_PS_MASK as usize) != 0
}

pub open spec fn usize2write(v: usize) -> bool {
    (v & PAGE_ENTRY_WRITE_MASK as usize) != 0
}

pub open spec fn usize2execute_disable(v: usize) -> bool {
    (v & PAGE_ENTRY_EXECUTE_MASK as usize) != 0
}

pub open spec fn usize2user(v: usize) -> bool {
    (v & PAGE_ENTRY_USER_MASK as usize) != 0
}

pub open spec fn spec_usize2page_entry_perm(v: usize) -> PageEntryPerm {
    PageEntryPerm {
        present: usize2present(v),
        ps: usize2ps(v),
        write: usize2write(v),
        execute_disable: usize2execute_disable(v),
        user: usize2user(v),
    }
}

#[verifier::external_body]
#[verifier(when_used_as_spec(spec_usize2page_entry_perm))]
pub fn usize2page_entry_perm(v: usize) -> (ret: PageEntryPerm)
    ensures
        ret =~= spec_usize2page_entry_perm(v),
        v == 0 ==> ret.present == false && ret.ps == false && ret.write == false
            && ret.execute_disable == false && ret.user == false,
{
    unimplemented!()
}

#[verifier::external_body]
#[verifier(when_used_as_spec(spec_usize2page_entry))]
pub fn usize2page_entry(v: usize) -> (ret: PageEntry)
    ensures
        ret =~= spec_usize2page_entry(v),
        v == 0 ==> ret.addr == 0 && ret.perm.present == false && ret.perm.ps == false
            && ret.perm.write == false && ret.perm.execute_disable == false && ret.perm.user
            == false,
{
    unimplemented!()
}
pub open spec fn spec_usize2page_entry(v: usize) -> PageEntry {
    PageEntry { addr: usize2pa(v), perm: usize2page_entry_perm(v) }
}

pub open spec fn spec_usize2pa(v: usize) -> PAddr {
    v & MEM_MASK as usize
}

#[verifier::external_body]
#[verifier(when_used_as_spec(spec_usize2pa))]
pub fn usize2pa(v: usize) -> (ret: PAddr)
    ensures
        ret =~= spec_usize2pa(v),
        MEM_valid(ret),
{
    unimplemented!()
}


// File: pagetable/pagetable_spec.rs
pub struct PageTable {
    pub cr3: PageMapPtr,
    pub pcid: Option<Pcid>,
    pub ioid: Option<IOid>,
    pub kernel_l4_end: usize,
    pub l4_table: Tracked<Map<PageMapPtr, PointsTo<PageMap>>>,
    pub l3_rev_map: Ghost<Map<PageMapPtr, (L4Index)>>,
    pub l3_tables: Tracked<Map<PageMapPtr, PointsTo<PageMap>>>,
    pub l2_rev_map: Ghost<Map<PageMapPtr, (L4Index, L3Index)>>,
    pub l2_tables: Tracked<Map<PageMapPtr, PointsTo<PageMap>>>,
    pub l1_rev_map: Ghost<Map<PageMapPtr, (L4Index, L3Index, L2Index)>>,
    pub l1_tables: Tracked<Map<PageMapPtr, PointsTo<PageMap>>>,
    pub mapping_4k: Ghost<Map<VAddr, MapEntry>>,
    pub mapping_2m: Ghost<Map<VAddr, MapEntry>>,
    pub mapping_1g: Ghost<Map<VAddr, MapEntry>>,
    pub kernel_entries: Ghost<Seq<PageEntry>>,
    pub tlb_mapping_4k: Ghost<Seq<Map<VAddr, MapEntry>>>,
    pub tlb_mapping_2m: Ghost<Seq<Map<VAddr, MapEntry>>>,
    pub tlb_mapping_1g: Ghost<Seq<Map<VAddr, MapEntry>>>,
}

impl PageTable {

    pub open   spec fn page_closure(&self) -> Set<PagePtr> {
        self.l3_tables@.dom() + self.l2_tables@.dom() + self.l1_tables@.dom() + self.l4_table@.dom()
    }

    pub open   spec fn mapping_4k(&self) -> Map<VAddr, MapEntry> {
        self.mapping_4k@
    }

    pub open   spec fn mapping_2m(&self) -> Map<VAddr, MapEntry> {
        self.mapping_2m@
    }

    pub open   spec fn mapping_1g(&self) -> Map<VAddr, MapEntry> {
        self.mapping_1g@
    }

    pub open   spec fn pcid_ioid_wf(&self) -> bool {
        self.pcid.is_Some() != self.ioid.is_Some()
    }

    pub open   spec fn tlb_wf(&self) -> bool {
        &&& self.tlb_mapping_4k@.len() == NUM_CPUS
        &&& self.tlb_mapping_2m@.len() == NUM_CPUS
        &&& self.tlb_mapping_1g@.len() == NUM_CPUS
    }

    pub open   spec fn tlb_submap_of_mapping(&self) -> bool {
        forall|cpu_id: CpuId|
            #![auto]
            0 <= cpu_id < NUM_CPUS ==> self.tlb_mapping_4k@[cpu_id as int].submap_of(
                self.mapping_4k@,
            ) && self.tlb_mapping_2m@[cpu_id as int].submap_of(self.mapping_2m@)
                && self.tlb_mapping_1g@[cpu_id as int].submap_of(self.mapping_1g@)
    }

    pub open   spec fn wf_l4(&self) -> bool {
        // &&&
        // self.cr3 != 0
        &&& self.l4_table@.dom() =~= Set::<PageMapPtr>::empty().insert(self.cr3)
        &&& self.cr3 == self.l4_table@[self.cr3].addr()
        &&& self.l4_table@[self.cr3].is_init()
        &&& self.l4_table@[self.cr3].value().wf()
        //L4 table only maps to L3
        &&& forall|i: L4Index|
         // #![trigger self.l4_table@[self.cr3].value()[i].perm.present]

            #![trigger self.l2_tables@.dom().contains(self.l4_table@[self.cr3].value()[i].addr)]
            #![trigger self.l1_tables@.dom().contains(self.l4_table@[self.cr3].value()[i].addr)]
            self.kernel_l4_end <= i < 512 && self.l4_table@[self.cr3].value()[i].perm.present
                ==> self.l2_tables@.dom().contains(self.l4_table@[self.cr3].value()[i].addr)
                == false && self.l1_tables@.dom().contains(self.l4_table@[self.cr3].value()[i].addr)
                == false && self.cr3
                != self.l4_table@[self.cr3].value()[i].addr
        // no self mapping
        &&& forall|i: L4Index|
         // #![trigger self.l4_table@[self.cr3].value()[i].perm.present]

            #![trigger self.l4_table@[self.cr3].value()[i].addr]
            self.kernel_l4_end <= i < 512 && self.l4_table@[self.cr3].value()[i].perm.present
                ==> self.cr3
                != self.l4_table@[self.cr3].value()[i].addr
        //all l4 points to valid l3 tables
        &&& forall|i: L4Index|
            #![trigger self.l3_tables@.dom().contains(self.l4_table@[self.cr3].value()[i].addr)]
            self.kernel_l4_end <= i < 512 && self.l4_table@[self.cr3].value()[i].perm.present
                && !self.l4_table@[self.cr3].value()[i].perm.ps ==> self.l3_tables@.dom().contains(
                self.l4_table@[self.cr3].value()[i].addr,
            )
            //no hugepage in L4 (hardware limit)
        &&& forall|i: L4Index|
            #![trigger self.l4_table@[self.cr3].value()[i].perm.ps]
            self.kernel_l4_end <= i < 512 && self.l4_table@[self.cr3].value()[i].perm.present
                ==> !self.l4_table@[self.cr3].value()[i].perm.ps
    }

    pub open   spec fn disjoint_l4(&self) -> bool {
        &&& forall|i: L4Index, j: L4Index|
         // #![trigger self.l4_table@[self.cr3].value()[i].perm.present, self.l4_table@[self.cr3].value()[j].perm.present]

            #![trigger self.l4_table@[self.cr3].value()[i].perm.present, self.l4_table@[self.cr3].value()[j].perm.present, self.l4_table@[self.cr3].value()[i].addr, self.l4_table@[self.cr3].value()[j].addr]
            i != j && self.kernel_l4_end <= i < 512
                && self.l4_table@[self.cr3].value()[i].perm.present && self.kernel_l4_end <= j < 512
                && self.l4_table@[self.cr3].value()[j].perm.present
                ==> self.l4_table@[self.cr3].value()[i].addr
                != self.l4_table@[self.cr3].value()[j].addr
    }

    pub open   spec fn wf_l3(&self) -> bool {
        // &&&
        // self.l3_tables@.dom().contains(0) == false
        &&& forall|p: PageMapPtr|
            #![trigger self.l3_tables@[p].addr()]
            self.l3_tables@.dom().contains(p) ==> self.l3_tables@[p].addr() == p
        &&& forall|p: PageMapPtr|
            #![trigger self.l3_tables@[p].is_init()]
            self.l3_tables@.dom().contains(p) ==> self.l3_tables@[p].is_init()
        &&& forall|p: PageMapPtr|
            #![trigger self.l3_tables@[p].value().wf()]
            self.l3_tables@.dom().contains(p) ==> self.l3_tables@[p].value().wf()
        &&& forall|p: PageMapPtr|
            #![trigger self.l3_rev_map@.dom().contains(p)]
            #![trigger self.l3_rev_map@[p]]
            self.l3_tables@.dom().contains(p) ==> self.kernel_l4_end <= self.l3_rev_map@[p] < 512
                && self.l3_rev_map@.dom().contains(p) && self.spec_resolve_mapping_l4(
                self.l3_rev_map@[p],
            ).is_Some() && self.spec_resolve_mapping_l4(self.l3_rev_map@[p]).get_Some_0().addr
                == p
            //L3 tables does not map to L4 or L1
        &&& forall|p: PageMapPtr, i: L3Index|
            #![trigger self.l3_tables@.dom().contains(p), self.l3_tables@[p].value()[i].perm.present, self.l3_tables@.dom().contains(self.l3_tables@[p].value()[i].addr)]
            #![trigger self.l3_tables@.dom().contains(p), self.l3_tables@[p].value()[i].perm.present, self.l1_tables@.dom().contains(self.l3_tables@[p].value()[i].addr)]
            #![trigger self.l3_tables@.dom().contains(p), self.l3_tables@[p].value()[i].perm.present, self.l3_tables@[p].value()[i].addr]
            self.l3_tables@.dom().contains(p) && 0 <= i < 512
                && self.l3_tables@[p].value()[i].perm.present ==> self.l3_tables@.dom().contains(
                self.l3_tables@[p].value()[i].addr,
            ) == false && self.l1_tables@.dom().contains(self.l3_tables@[p].value()[i].addr)
                == false && self.cr3
                != self.l3_tables@[p].value()[i].addr
        // all l3 points to valid l2 tables
        &&& forall|p: PageMapPtr, i: L3Index|
            #![trigger self.l3_tables@[p].value()[i].perm.present, self.l3_tables@[p].value()[i].perm.ps, self.l2_tables@.dom().contains(self.l3_tables@[p].value()[i].addr)]
        // #![trigger self.l2_tables@.dom().contains(self.l3_tables@[p].value()[i].addr)]

            self.l3_tables@.dom().contains(p) && 0 <= i < 512
                && self.l3_tables@[p].value()[i].perm.present
                && !self.l3_tables@[p].value()[i].perm.ps ==> self.l2_tables@.dom().contains(
                self.l3_tables@[p].value()[i].addr,
            )
    }

    pub open   spec fn disjoint_l3(&self) -> bool {
            //L3 tables unique within
        &&& forall|p: PageMapPtr, l3i: L3Index, l3j: L3Index|
            // #![trigger self.l3_tables@.dom().contains(p), self.l3_tables@[p].value()[l3i].addr, self.l3_tables@[p].value()[l3j].addr, self.l3_tables@[p].value()[l3i].perm.ps, self.l3_tables@[p].value()[l3j].perm.ps, self.l3_tables@[p].value()[l3i].addr, self.l3_tables@[p].value()[l3j].addr]
            // #![trigger self.l3_tables@[p].value()[l3i].perm.present, self.l3_tables@[p].value()[l3j].perm.present]
            #![trigger self.l3_tables@[p].value()[l3i].addr,
                self.l3_tables@[p].value()[l3j].addr]
            self.l3_tables@.dom().contains(p) && l3i != l3j && 0 <= l3i < 512 && 0 <= l3j < 512
                && self.l3_tables@[p].value()[l3i].perm.present
                && self.l3_tables@[p].value()[l3j].perm.present
                && !self.l3_tables@[p].value()[l3i].perm.ps
                && !self.l3_tables@[p].value()[l3j].perm.ps ==> self.l3_tables@[p].value()[l3i].addr
                != self.l3_tables@[p].value()[l3j].addr
            //L3 tables are disjoint
        &&& forall|pi: PageMapPtr, pj: PageMapPtr, l3i: L3Index, l3j: L3Index|
            // #![trigger self.l3_tables@.dom().contains(pi), self.l3_tables@.dom().contains(pj), self.l3_tables@[pi].value()[l3i].addr, self.l3_tables@[pj].value()[l3j].addr, self.l3_tables@[pi].value()[l3i].perm.ps, self.l3_tables@[pj].value()[l3j].perm.ps, self.l3_tables@[pi].value()[l3i].perm.present, self.l3_tables@[pj].value()[l3j].perm.present]
            // #![trigger self.l3_tables@[pi].value()[l3i].perm.present, self.l3_tables@[pj].value()[l3j].perm.present]
            #![trigger self.l3_tables@[pi].value()[l3i].addr,
                self.l3_tables@[pj].value()[l3j].addr]
            pi != pj && self.l3_tables@.dom().contains(pi) && self.l3_tables@.dom().contains(pj)
                && 0 <= l3i < 512 && 0 <= l3j < 512 && self.l3_tables@[pi].value()[l3i].perm.present
                && self.l3_tables@[pj].value()[l3j].perm.present
                && !self.l3_tables@[pi].value()[l3i].perm.ps
                && !self.l3_tables@[pj].value()[l3j].perm.ps
                ==> self.l3_tables@[pi].value()[l3i].addr
                != self.l3_tables@[pj].value()[l3j].addr
    }

    pub open   spec fn wf_l2(&self) -> bool {
        // &&&
        // self.l2_tables@.dom().contains(0) == false
        &&& forall|p: PageMapPtr|
            #![trigger self.l2_tables@[p].addr()]
            self.l2_tables@.dom().contains(p) ==> self.l2_tables@[p].addr() == p
        &&& forall|p: PageMapPtr|
            #![trigger self.l2_tables@[p].is_init()]
            self.l2_tables@.dom().contains(p) ==> self.l2_tables@[p].is_init()
        &&& forall|p: PageMapPtr|
            #![trigger self.l2_tables@[p].value().wf()]
            self.l2_tables@.dom().contains(p)
                ==> self.l2_tables@[p].value().wf()
        // all l2 tables exist in l3 mapping
        &&& forall|p: PageMapPtr|
            #![trigger self.l2_rev_map@[p]]
            #![trigger self.l2_rev_map@.dom().contains(p)]
            self.l2_tables@.dom().contains(p) ==> self.l2_rev_map@.dom().contains(p)
                && self.kernel_l4_end <= self.l2_rev_map@[p].0 < 512 && 0 <= self.l2_rev_map@[p].1
                < 512 && self.spec_resolve_mapping_l3(
                self.l2_rev_map@[p].0,
                self.l2_rev_map@[p].1,
            ).is_Some() && self.spec_resolve_mapping_l3(
                self.l2_rev_map@[p].0,
                self.l2_rev_map@[p].1,
            ).get_Some_0().addr == p
            // L2 does not map to L4, L3, or self
        &&& forall|p: PageMapPtr, i: L2Index|
            #![trigger self.l2_tables@.dom().contains(p), self.l2_tables@[p].value()[i].perm.present, self.l2_tables@.dom().contains(self.l2_tables@[p].value()[i].addr)]
            #![trigger self.l2_tables@.dom().contains(p), self.l2_tables@[p].value()[i].perm.present, self.l3_tables@.dom().contains(self.l2_tables@[p].value()[i].addr)]
            #![trigger self.l2_tables@.dom().contains(p), self.l2_tables@[p].value()[i].perm.present, self.l2_tables@[p].value()[i].addr]
            self.l2_tables@.dom().contains(p) && 0 <= i < 512
                && self.l2_tables@[p].value()[i].perm.present ==> self.l2_tables@.dom().contains(
                self.l2_tables@[p].value()[i].addr,
            ) == false && self.l3_tables@.dom().contains(self.l2_tables@[p].value()[i].addr)
                == false && self.cr3
                != self.l2_tables@[p].value()[i].addr
        // all l2 points to valid l1 tables
        &&& forall|p: PageMapPtr, i: L2Index|
            #![trigger self.l1_tables@.dom().contains(self.l2_tables@[p].value()[i].addr), self.l2_tables@[p].value()[i].perm.present, self.l2_tables@[p].value()[i].perm.ps]
            self.l2_tables@.dom().contains(p) && 0 <= i < 512
                && self.l2_tables@[p].value()[i].perm.present
                && !self.l2_tables@[p].value()[i].perm.ps ==> self.l1_tables@.dom().contains(
                self.l2_tables@[p].value()[i].addr,
            )
    }

    pub open   spec fn disjoint_l2(&self) -> bool {
            // L2 mappings are unique within
        // &&& forall|p: PageMapPtr, l2i: L2Index, l2j: L2Index|
        //     // #![trigger self.l2_tables@.dom().contains(p), self.l2_tables@[p].value()[l2i].perm.present, self.l2_tables@[p].value()[l2j].perm.present, self.l2_tables@[p].value()[l2i].perm.ps, self.l2_tables@[p].value()[l2j].perm.ps]
        //     self.l2_tables@.dom().contains(p) && l2i != l2j && 0 <= l2i < 512 && 0 <= l2j < 512
        //         && self.l2_tables@[p].value()[l2i].perm.present
        //         && self.l2_tables@[p].value()[l2j].perm.present
        //         && !self.l2_tables@[p].value()[l2i].perm.ps
        //         && !self.l2_tables@[p].value()[l2j].perm.ps ==> self.l2_tables@[p].value()[l2i].addr
        //         != self.l2_tables@[p].value()[l2j].addr
            // L2 mappings are unique
        &&& forall|pi: PageMapPtr, pj: PageMapPtr, l2i: L2Index, l2j: L2Index|
            // #![trigger self.l2_tables@.dom().contains(pi), self.l2_tables@.dom().contains(pj),
            //     self.l2_tables@[pi].value()[l2i].perm.present, self.l2_tables@[pj].value()[l2j].perm.present,
            //     self.l2_tables@[pi].value()[l2i].perm.ps, self.l2_tables@[pj].value()[l2j].perm.ps, 
            //     self.l2_tables@[pi].value()[l2i].addr,
            //     self.l2_tables@[pj].value()[l2j].addr]
            #![trigger self.l2_tables@[pi].value()[l2i].addr, self.l2_tables@[pj].value()[l2j].addr]
            self.l2_tables@.dom().contains(pi) && self.l2_tables@.dom().contains(pj)
                && 0 <= l2i < 512 && 0 <= l2j < 512 && self.l2_tables@[pi].value()[l2i].perm.present
                && self.l2_tables@[pj].value()[l2j].perm.present
                && !self.l2_tables@[pi].value()[l2i].perm.ps
                && !self.l2_tables@[pj].value()[l2j].perm.ps
                ==> 
                ( pi != pj ==> self.l2_tables@[pi].value()[l2i].addr != self.l2_tables@[pj].value()[l2j].addr)
                &&
                ( pi == pj && l2i != l2j ==> self.l2_tables@[pi].value()[l2i].addr != self.l2_tables@[pj].value()[l2j].addr)
    }

    pub open   spec fn wf_l1(&self) -> bool {
        // &&&
        // self.l1_tables@.dom().contains(0) == false
        &&& forall|p: PageMapPtr|
            #![trigger self.l1_tables@[p].addr()]
            self.l1_tables@.dom().contains(p) ==> self.l1_tables@[p].addr() == p
        &&& forall|p: PageMapPtr|
            #![trigger self.l1_tables@[p].is_init()]
            self.l1_tables@.dom().contains(p) ==> self.l1_tables@[p].is_init()
        &&& forall|p: PageMapPtr|
            #![trigger self.l1_tables@[p].value().wf()]
            self.l1_tables@.dom().contains(p)
                ==> self.l1_tables@[p].value().wf()
        // all l1 tables exist in l2 mapping
        &&& forall|p: PageMapPtr|
            #![trigger self.l1_rev_map@.dom().contains(p)]
            #![trigger self.l1_rev_map@[p]]
            self.l1_tables@.dom().contains(p) ==> self.l1_rev_map@.dom().contains(p)
                && self.kernel_l4_end <= self.l1_rev_map@[p].0 < 512 && 0 <= self.l1_rev_map@[p].1
                < 512 && 0 <= self.l1_rev_map@[p].2 < 512 && self.spec_resolve_mapping_l2(
                self.l1_rev_map@[p].0,
                self.l1_rev_map@[p].1,
                self.l1_rev_map@[p].2,
            ).is_Some() && self.spec_resolve_mapping_l2(
                self.l1_rev_map@[p].0,
                self.l1_rev_map@[p].1,
                self.l1_rev_map@[p].2,
            ).get_Some_0().addr == p
            // no l1 tables map to other levels
        &&& forall|p: PageMapPtr, i: L1Index|
            #![trigger self.l1_tables@.dom().contains(p), self.l1_tables@[p].value()[i].perm.present, self.l2_tables@.dom().contains(self.l1_tables@[p].value()[i].addr)]
            #![trigger self.l1_tables@.dom().contains(p), self.l1_tables@[p].value()[i].perm.present, self.l3_tables@.dom().contains(self.l1_tables@[p].value()[i].addr)]
            #![trigger self.l1_tables@.dom().contains(p), self.l1_tables@[p].value()[i].perm.present, self.l1_tables@[p].value()[i].addr]
            self.l1_tables@.dom().contains(p) && 0 <= i < 512
                && self.l1_tables@[p].value()[i].perm.present ==> self.l2_tables@.dom().contains(
                self.l1_tables@[p].value()[i].addr,
            ) == false && self.l3_tables@.dom().contains(self.l1_tables@[p].value()[i].addr)
                == false && self.cr3
                != self.l1_tables@[p].value()[i].addr
        // no hugepage in l1
        &&& forall|p: PageMapPtr, i: L1Index|
            #![trigger self.l1_tables@[p].value()[i].perm.ps]
            self.l1_tables@.dom().contains(p) && 0 <= i < 512
                && self.l1_tables@[p].value()[i].perm.present
                ==> !self.l1_tables@[p].value()[i].perm.ps
    }

    pub open   spec fn user_only(&self) -> bool {
        &&& forall|i: L4Index|
            #![trigger self.l4_table@[self.cr3].value()[i].perm, self.l4_table@[self.cr3].value()[i].perm.user]
            self.kernel_l4_end <= i < 512 && self.l4_table@[self.cr3].value()[i].perm.present
                ==> self.l4_table@[self.cr3].value()[i].perm.user
        &&& forall|p: PageMapPtr, i: L3Index|
            #![trigger self.l3_tables@[p].value()[i].perm, self.l3_tables@[p].value()[i].perm.user]
            self.l3_tables@.dom().contains(p) && 0 <= i < 512
                && self.l3_tables@[p].value()[i].perm.present
                ==> self.l3_tables@[p].value()[i].perm.user
        &&& forall|p: PageMapPtr, i: L2Index|
            #![trigger self.l2_tables@[p].value()[i].perm, self.l2_tables@[p].value()[i].perm.user]
            self.l2_tables@.dom().contains(p) && 0 <= i < 512
                && self.l2_tables@[p].value()[i].perm.present
                ==> self.l2_tables@[p].value()[i].perm.user
        &&& forall|p: PageMapPtr, i: L1Index|
            #![trigger self.l1_tables@[p].value()[i].perm, self.l1_tables@[p].value()[i].perm.user]
            self.l1_tables@.dom().contains(p) && 0 <= i < 512
                && self.l1_tables@[p].value()[i].perm.present
                ==> self.l1_tables@[p].value()[i].perm.user
    }

    pub open   spec fn present_or_zero(&self) -> bool {
        &&& forall|i: L4Index|
            #![trigger self.l4_table@[self.cr3].value()[i].is_empty()]
            self.kernel_l4_end <= i < 512 && !self.l4_table@[self.cr3].value()[i].perm.present
                ==> self.l4_table@[self.cr3].value()[i].is_empty()
        &&& forall|p: PageMapPtr, i: L3Index|
            #![trigger self.l3_tables@[p].value()[i].is_empty()]
            self.l3_tables@.dom().contains(p) && 0 <= i < 512
                && !self.l3_tables@[p].value()[i].perm.present
                ==> self.l3_tables@[p].value()[i].is_empty()
        &&& forall|p: PageMapPtr, i: L2Index|
            #![trigger self.l2_tables@[p].value()[i].is_empty()]
            self.l2_tables@.dom().contains(p) && 0 <= i < 512
                && !self.l2_tables@[p].value()[i].perm.present
                ==> self.l2_tables@[p].value()[i].is_empty()
        &&& forall|p: PageMapPtr, i: L1Index|
            #![trigger self.l1_tables@[p].value()[i].is_empty()]
            self.l1_tables@.dom().contains(p) && 0 <= i < 512
                && !self.l1_tables@[p].value()[i].perm.present
                ==> self.l1_tables@[p].value()[i].is_empty()
    }

    pub open   spec fn rwx_upper_level_entries(&self) -> bool {
        &&& forall|i: L4Index|
            #![trigger self.l4_table@[self.cr3].value()[i].perm]
            // #![trigger self.l4_table@[self.cr3].value()[i].perm.execute_disable]
            self.kernel_l4_end <= i < 512 && self.l4_table@[self.cr3].value()[i].perm.present
                ==> self.l4_table@[self.cr3].value()[i].perm.write
                && !self.l4_table@[self.cr3].value()[i].perm.execute_disable
        &&& forall|p: PageMapPtr, i: L3Index|
            #![trigger self.l3_tables@[p].value()[i].perm]
            // #![trigger self.l3_tables@[p].value()[i].perm.execute_disable]
            self.l3_tables@.dom().contains(p) && 0 <= i < 512
                && self.l3_tables@[p].value()[i].perm.present
                && !self.l3_tables@[p].value()[i].perm.ps
                ==> self.l3_tables@[p].value()[i].perm.write
                && !self.l3_tables@[p].value()[i].perm.execute_disable
        &&& forall|p: PageMapPtr, i: L2Index|
            #![trigger  self.l2_tables@[p].value()[i].perm]
            // #![trigger self.l2_tables@[p].value()[i].perm.execute_disable]
            self.l2_tables@.dom().contains(p) && 0 <= i < 512
                && self.l2_tables@[p].value()[i].perm.present
                && !self.l2_tables@[p].value()[i].perm.ps
                ==> self.l2_tables@[p].value()[i].perm.write
                && !self.l2_tables@[p].value()[i].perm.execute_disable
    }

    pub open   spec fn table_pages_wf(&self) -> bool {
        &&& page_ptr_valid(self.cr3)
        &&& forall|p: PageMapPtr|
            #![trigger self.l3_tables@.dom().contains(p), page_ptr_valid(p)]
            self.l3_tables@.dom().contains(p) ==> page_ptr_valid(p)
        &&& forall|p: PageMapPtr|
            #![trigger self.l2_tables@.dom().contains(p), page_ptr_valid(p)]
            self.l2_tables@.dom().contains(p) ==> page_ptr_valid(p)
        &&& forall|p: PageMapPtr|
            #![trigger self.l1_tables@.dom().contains(p), page_ptr_valid(p)]
            self.l1_tables@.dom().contains(p) ==> page_ptr_valid(p)
        &&&
        self.l4_table@.dom().disjoint(self.l3_tables@.dom())
        &&&
        self.l4_table@.dom().disjoint(self.l2_tables@.dom())
        &&&
        self.l4_table@.dom().disjoint(self.l1_tables@.dom())
        &&&
        self.l3_tables@.dom().disjoint(self.l2_tables@.dom())
        &&&
        self.l3_tables@.dom().disjoint(self.l1_tables@.dom())
        &&&
        self.l2_tables@.dom().disjoint(self.l1_tables@.dom())
    }

    pub open   spec fn spec_resolve_mapping_l4(&self, l4i: L4Index) -> Option<PageEntry>
        recommends
            self.kernel_l4_end <= l4i < 512,
    {
        if self.l4_table@[self.cr3].value()[l4i].perm.present || l4i < self.kernel_l4_end {
            Some(self.l4_table@[self.cr3].value()[l4i])
        } else {
            None
        }
    }

    pub open   spec fn spec_resolve_mapping_1g_l3(&self, l4i: L4Index, l3i: L3Index) -> Option<
        PageEntry,
    >
        recommends
            self.kernel_l4_end <= l4i < 512,
            0 <= l3i < 512,
    {
        if self.spec_resolve_mapping_l4(l4i).is_None() {
            None
        } else if !self.l3_tables@[self.spec_resolve_mapping_l4(
            l4i,
        ).get_Some_0().addr].value()[l3i].perm.present
            || !self.l3_tables@[self.spec_resolve_mapping_l4(
            l4i,
        ).get_Some_0().addr].value()[l3i].perm.ps {
            None
        } else {
            Some(self.l3_tables@[self.spec_resolve_mapping_l4(l4i).get_Some_0().addr].value()[l3i])
        }
    }

    pub open   spec fn spec_resolve_mapping_l3(&self, l4i: L4Index, l3i: L3Index) -> Option<
        PageEntry,
    >
        recommends
            self.kernel_l4_end <= l4i < 512,
            0 <= l3i < 512,
    {
        if self.spec_resolve_mapping_l4(l4i).is_None() {
            None
        } else if !self.l3_tables@[self.spec_resolve_mapping_l4(
            l4i,
        ).get_Some_0().addr].value()[l3i].perm.present
            || self.l3_tables@[self.spec_resolve_mapping_l4(
            l4i,
        ).get_Some_0().addr].value()[l3i].perm.ps {
            None
        } else {
            Some(self.l3_tables@[self.spec_resolve_mapping_l4(l4i).get_Some_0().addr].value()[l3i])
        }
    }

    pub open   spec fn spec_resolve_mapping_2m_l2(
        &self,
        l4i: L4Index,
        l3i: L3Index,
        l2i: L2Index,
    ) -> Option<PageEntry>
        recommends
            self.kernel_l4_end <= l4i < 512,
            0 <= l3i < 512,
            0 <= l2i < 512,
    {
        if self.spec_resolve_mapping_l3(l4i, l3i).is_None() {
            None
        } else if !self.l2_tables@[self.spec_resolve_mapping_l3(
            l4i,
            l3i,
        ).get_Some_0().addr].value()[l2i].perm.present
            || !self.l2_tables@[self.spec_resolve_mapping_l3(
            l4i,
            l3i,
        ).get_Some_0().addr].value()[l2i].perm.ps {
            None
        } else {
            Some(
                self.l2_tables@[self.spec_resolve_mapping_l3(
                    l4i,
                    l3i,
                ).get_Some_0().addr].value()[l2i],
            )
        }
    }

    pub open   spec fn spec_resolve_mapping_l2(
        &self,
        l4i: L4Index,
        l3i: L3Index,
        l2i: L2Index,
    ) -> Option<PageEntry>
        recommends
            self.kernel_l4_end <= l4i < 512,
            0 <= l3i < 512,
            0 <= l2i < 512,
    {
        if self.spec_resolve_mapping_l3(l4i, l3i).is_None() {
            None
        } else if !self.l2_tables@[self.spec_resolve_mapping_l3(
            l4i,
            l3i,
        ).get_Some_0().addr].value()[l2i].perm.present
            || self.l2_tables@[self.spec_resolve_mapping_l3(
            l4i,
            l3i,
        ).get_Some_0().addr].value()[l2i].perm.ps {
            None
        } else {
            Some(
                self.l2_tables@[self.spec_resolve_mapping_l3(
                    l4i,
                    l3i,
                ).get_Some_0().addr].value()[l2i],
            )
        }
    }

    pub open   spec fn spec_resolve_mapping_4k_l1(
        &self,
        l4i: L4Index,
        l3i: L3Index,
        l2i: L2Index,
        l1i: L1Index,
    ) -> Option<PageEntry>
        recommends
            self.kernel_l4_end <= l4i < 512,
            0 <= l3i < 512,
            0 <= l2i < 512,
            0 <= l1i < 512,
    {
        if self.spec_resolve_mapping_l2(l4i, l3i, l2i).is_None() {
            None
        } else if !self.l1_tables@[self.spec_resolve_mapping_l2(
            l4i,
            l3i,
            l2i,
        ).get_Some_0().addr].value()[l1i].perm.present {
            None
        } else {
            Some(
                self.l1_tables@[self.spec_resolve_mapping_l2(
                    l4i,
                    l3i,
                    l2i,
                ).get_Some_0().addr].value()[l1i],
            )
        }

    }

    pub open   spec fn wf_mapping_4k(&self) -> bool {
        &&& forall|va: VAddr|
            #![trigger va_4k_valid(va), self.mapping_4k@.dom().contains(va)]
            self.mapping_4k@.dom().contains(va) ==> va_4k_valid(va)
        &&& forall|l4i: L4Index, l3i: L3Index, l2i: L2Index, l1i: L2Index|
            #![trigger self.mapping_4k@[spec_index2va((l4i,l3i,l2i,l1i))]]
            #![trigger self.spec_resolve_mapping_4k_l1(l4i,l3i,l2i,l1i)]
            self.kernel_l4_end <= l4i < 512 && 0 <= l3i < 512 && 0 <= l2i < 512 && 0 <= l1i < 512
                ==> self.mapping_4k@.dom().contains(spec_index2va((l4i, l3i, l2i, l1i)))
                == self.spec_resolve_mapping_4k_l1(l4i, l3i, l2i, l1i).is_Some()
        &&& forall|l4i: L4Index, l3i: L3Index, l2i: L2Index, l1i: L2Index|
            #![trigger self.mapping_4k@[spec_index2va((l4i,l3i,l2i,l1i))]]
            self.kernel_l4_end <= l4i < 512 && 0 <= l3i < 512 && 0 <= l2i < 512 && 0 <= l1i < 512
                && self.spec_resolve_mapping_4k_l1(l4i, l3i, l2i, l1i).is_Some()
                ==> self.mapping_4k@[spec_index2va((l4i, l3i, l2i, l1i))].addr
                == self.spec_resolve_mapping_4k_l1(l4i, l3i, l2i, l1i).get_Some_0().addr
                && self.mapping_4k@[spec_index2va((l4i, l3i, l2i, l1i))].write
                == self.spec_resolve_mapping_4k_l1(l4i, l3i, l2i, l1i).get_Some_0().perm.write
                && self.mapping_4k@[spec_index2va((l4i, l3i, l2i, l1i))].execute_disable
                == self.spec_resolve_mapping_4k_l1(
                l4i,
                l3i,
                l2i,
                l1i,
            ).get_Some_0().perm.execute_disable
        &&& forall|va: VAddr|
            #![trigger self.mapping_4k@.dom().contains(va), page_ptr_valid(self.mapping_4k@[va].addr)]
            self.mapping_4k@.dom().contains(va) ==> page_ptr_valid(self.mapping_4k@[va].addr)
    }

    pub open   spec fn wf_mapping_2m(&self) -> bool {
        &&& forall|va: VAddr|
            #![trigger va_2m_valid(va), self.mapping_2m@.dom().contains(va)]
            self.mapping_2m@.dom().contains(va) ==> va_2m_valid(va)
        &&& forall|l4i: L4Index, l3i: L3Index, l2i: L2Index|
            #![trigger self.mapping_2m@[spec_index2va((l4i,l3i,l2i,0))]]
            #![trigger self.spec_resolve_mapping_2m_l2(l4i,l3i,l2i)]
            self.kernel_l4_end <= l4i < 512 && 0 <= l3i < 512 && 0 <= l2i < 512
                ==> self.mapping_2m@.dom().contains(spec_index2va((l4i, l3i, l2i, 0)))
                == self.spec_resolve_mapping_2m_l2(l4i, l3i, l2i).is_Some()
        &&& forall|l4i: L4Index, l3i: L3Index, l2i: L2Index|
            #![trigger self.mapping_2m@[spec_index2va((l4i,l3i,l2i,0))]]
            self.kernel_l4_end <= l4i < 512 && 0 <= l3i < 512 && 0 <= l2i < 512
                && self.spec_resolve_mapping_2m_l2(l4i, l3i, l2i).is_Some()
                ==> self.mapping_2m@[spec_index2va((l4i, l3i, l2i, 0))].addr
                == self.spec_resolve_mapping_2m_l2(l4i, l3i, l2i).get_Some_0().addr
                && self.mapping_2m@[spec_index2va((l4i, l3i, l2i, 0))].write
                == self.spec_resolve_mapping_2m_l2(l4i, l3i, l2i).get_Some_0().perm.write
                && self.mapping_2m@[spec_index2va((l4i, l3i, l2i, 0))].execute_disable
                == self.spec_resolve_mapping_2m_l2(l4i, l3i, l2i).get_Some_0().perm.execute_disable
        &&& forall|va: VAddr|
            #![trigger self.mapping_2m@.dom().contains(va), page_ptr_2m_valid(self.mapping_2m@[va].addr)]
            self.mapping_2m@.dom().contains(va) ==> page_ptr_2m_valid(self.mapping_2m@[va].addr)
    }

    pub open   spec fn wf_mapping_1g(&self) -> bool {
        &&& forall|va: VAddr|
            #![trigger va_1g_valid(va), self.mapping_1g@.dom().contains(va)]
            self.mapping_1g@.dom().contains(va) ==> va_1g_valid(va)
        &&& forall|l4i: L4Index, l3i: L3Index|
            #![trigger self.mapping_1g@[spec_index2va((l4i,l3i,0,0))]]
            #![trigger self.spec_resolve_mapping_1g_l3(l4i,l3i)]
            self.kernel_l4_end <= l4i < 512 && 0 <= l3i < 512 ==> self.mapping_1g@.dom().contains(
                spec_index2va((l4i, l3i, 0, 0)),
            ) == self.spec_resolve_mapping_1g_l3(l4i, l3i).is_Some()
        &&& forall|l4i: L4Index, l3i: L3Index|
            #![trigger self.mapping_1g@[spec_index2va((l4i,l3i,0,0))]]
            #![trigger self.spec_resolve_mapping_1g_l3(l4i,l3i)]
            self.kernel_l4_end <= l4i < 512 && 0 <= l3i < 512 && self.spec_resolve_mapping_1g_l3(
                l4i,
                l3i,
            ).is_Some() ==> self.mapping_1g@[spec_index2va((l4i, l3i, 0, 0))].addr
                == self.spec_resolve_mapping_1g_l3(l4i, l3i).get_Some_0().addr
                && self.mapping_1g@[spec_index2va((l4i, l3i, 0, 0))].write
                == self.spec_resolve_mapping_1g_l3(l4i, l3i).get_Some_0().perm.write
                && self.mapping_1g@[spec_index2va((l4i, l3i, 0, 0))].execute_disable
                == self.spec_resolve_mapping_1g_l3(l4i, l3i).get_Some_0().perm.execute_disable
        &&& forall|va: VAddr|
            #![trigger self.mapping_1g@.dom().contains(va), page_ptr_1g_valid(self.mapping_1g@[va].addr)]
            self.mapping_1g@.dom().contains(va) ==> page_ptr_1g_valid(self.mapping_1g@[va].addr)
    }

    pub open   spec fn kernel_entries_wf(&self) -> bool {
        &&& self.kernel_l4_end < 512
        &&& self.kernel_entries@.len() =~= self.kernel_l4_end as nat
        &&& forall|i: usize|
            #![trigger self.kernel_entries@[i as int]]
            0 <= i < self.kernel_l4_end ==> self.kernel_entries@[i as int]
                == self.l4_table@[self.cr3].value()[i]
    }

	#[verifier::external_body]
    pub closed   spec fn wf(&self) -> bool {
		unimplemented!()
	}


	#[verifier::external_body]
    pub closed   spec fn levels_wf(&self) -> bool {
		unimplemented!()
	}


	#[verifier::external_body]
    pub closed   spec fn disjoint_wf(&self) -> bool {
		unimplemented!()
	}


	#[verifier::external_body]
    pub closed   spec fn mappings_wf(&self) -> bool {
		unimplemented!()
	}


	#[verifier::external_body]
    pub closed   spec fn additonal_wf(&self) -> bool {
		unimplemented!()
	}


	#[verifier::external_body]
    pub broadcast proof fn reveal_page_table_wf(&self)
        ensures
            #[trigger] self.wf() <==> {
                &&& self.levels_wf()
                &&& self.disjoint_wf()
                &&& self.mappings_wf()
                &&& self.additonal_wf()
    },
	{
		unimplemented!()
	}

	#[verifier::external_body]
    pub broadcast proof fn reveal_page_table_levels_wf(&self)
        ensures
            #[trigger] self.levels_wf() <==> {
                &&& self.wf_l4()
                &&& self.wf_l3()
                &&& self.wf_l2()
                &&& self.wf_l1()
    },
	{
		unimplemented!()
	}

	#[verifier::external_body]
     pub broadcast proof fn reveal_page_table_disjoint_wf(&self)
        ensures
            #[trigger] self.disjoint_wf() <==> {
                &&& self.disjoint_l4()
                &&& self.disjoint_l3()
                &&& self.disjoint_l2()
     },
	{
		unimplemented!()
	}

	#[verifier::external_body]
    pub broadcast proof fn reveal_page_table_mappings_wf(&self)
        ensures
            #[trigger] self.mappings_wf() <==> {
                &&& self.wf_mapping_4k()
                &&& self.wf_mapping_2m()
                &&& self.wf_mapping_1g()
    },
	{
		unimplemented!()
	}

	#[verifier::external_body]
    pub broadcast proof fn reveal_page_table_addtional_wf(&self)
        ensures
            #[trigger] self.additonal_wf() <==> {
                &&& self.user_only()
                &&& self.rwx_upper_level_entries()
                &&& self.present_or_zero()
                // &&&
                // self.no_self_mapping()
                &&& self.table_pages_wf()
                &&& self.kernel_entries_wf()
                &&& self.pcid_ioid_wf()
                &&& self.tlb_wf()
                &&& self.tlb_submap_of_mapping()
    },
	{
		unimplemented!()
	}

}


impl PageTable {

	#[verifier::external_body]
    pub proof fn internal_resolve_disjoint(&self)
        requires
            self.wf(),
        ensures
            forall|l4i: L4Index, l4j: L4Index|
                #![trigger self.spec_resolve_mapping_l4(l4i), self.spec_resolve_mapping_l4(l4j)]
                self.kernel_l4_end <= l4i < 512 && self.kernel_l4_end <= l4j < 512 && l4i != l4j
                    && self.spec_resolve_mapping_l4(l4i).is_Some() && self.spec_resolve_mapping_l4(
                    l4j,
                ).is_Some() ==> self.spec_resolve_mapping_l4(l4i).get_Some_0().addr
                    != self.spec_resolve_mapping_l4(l4j).get_Some_0().addr,
            forall|l4i: L4Index, l3i: L3Index, l4j: L4Index, l3j: L3Index|
                #![trigger self.spec_resolve_mapping_l3(l4i,l3i), self.spec_resolve_mapping_l3(l4j,l3j)]
                self.kernel_l4_end <= l4i < 512 && 0 <= l3i < 512 && self.kernel_l4_end <= l4j < 512
                    && 0 <= l3j < 512 && (l4i, l3i) != (l4j, l3j) && self.spec_resolve_mapping_l3(
                    l4i,
                    l3i,
                ).is_Some() && self.spec_resolve_mapping_l3(l4j, l3j).is_Some()
                    ==> self.spec_resolve_mapping_l3(l4i, l3i).get_Some_0().addr
                    != self.spec_resolve_mapping_l3(l4j, l3j).get_Some_0().addr,
            forall|
                l4i: L4Index,
                l3i: L3Index,
                l2i: L3Index,
                l4j: L4Index,
                l3j: L3Index,
                l2j: L2Index,
            |
                #![trigger self.spec_resolve_mapping_l2(l4i,l3i,l2i), self.spec_resolve_mapping_l2(l4j,l3j,l2j)]
                self.kernel_l4_end <= l4i < 512 && 0 <= l3i < 512 && 0 <= l2i < 512
                    && self.kernel_l4_end <= l4j < 512 && 0 <= l3j < 512 && 0 <= l2j < 512 && (
                    l4i,
                    l3i,
                    l2i,
                ) != (l4j, l3j, l2j) && self.spec_resolve_mapping_l2(l4i, l3i, l2i).is_Some()
                    && self.spec_resolve_mapping_l2(l4j, l3j, l2j).is_Some()
                    ==> self.spec_resolve_mapping_l2(l4i, l3i, l2i).get_Some_0().addr
                    != self.spec_resolve_mapping_l2(l4j, l3j, l2j).get_Some_0().addr,
	{
		unimplemented!()
	}

}



// File: array.rs
pub struct Array<A, const N: usize>{
    pub seq: Ghost<Seq<A>>,
    pub ar: [A;N]
}

impl<A, const N: usize> Array<A, N> {

    #[verifier(inline)]
    pub open spec fn view(&self) -> Seq<A>{
        self.seq@
    }

    pub open spec fn wf(&self) -> bool{
        self.seq@.len() == N
    }

}



// File: pagetable/pagemap_util_t.rs
	#[verifier::external_body]
#[verifier(external_body)]
pub fn page_map_set(
    page_map_ptr: PageMapPtr,
    Tracked(page_map_perm): Tracked<&mut PointsTo<PageMap>>,
    index: usize,
    value: PageEntry,
)
    requires
        old(page_map_perm).addr() == page_map_ptr,
        old(page_map_perm).is_init(),
        old(page_map_perm).value().wf(),
        value.perm.present ==> MEM_valid(value.addr),
        value.perm.present == false ==> value.is_empty(),
        0 <= index < 512,
    ensures
        page_map_perm.addr() == page_map_ptr,
        page_map_perm.is_init(),
        page_map_perm.value().wf(),
        forall|i: usize|
            #![trigger page_map_perm.value()[i]]
            0 <= i < 512 && i != index ==> page_map_perm.value()[i] =~= old(
                page_map_perm,
            ).value()[i],
        page_map_perm.value()[index] =~= value,
	{
		unimplemented!()
	}


// File: pagetable/pagetable_impl_base.rs
impl PageTable {

    pub fn map_4k_page(
        &mut self,
        target_l4i: L4Index,
        target_l3i: L3Index,
        target_l2i: L2Index,
        target_l1i: L2Index,
        target_l1_p: PageMapPtr,
        target_entry: &MapEntry,
    )
        requires
            old(self).wf(),
            old(self).kernel_l4_end <= target_l4i < 512,
            0 <= target_l3i < 512,
            0 <= target_l2i < 512,
            0 <= target_l1i < 512,
            old(self).spec_resolve_mapping_l2(target_l4i, target_l3i, target_l2i).is_Some(),
            old(self).spec_resolve_mapping_l2(target_l4i, target_l3i, target_l2i).get_Some_0().addr
                == target_l1_p,
            old(self).spec_resolve_mapping_4k_l1(
                target_l4i,
                target_l3i,
                target_l2i,
                target_l1i,
            ).is_None() || old(self).mapping_4k().dom().contains(
                spec_index2va((target_l4i, target_l3i, target_l2i, target_l1i)),
            ) == false,
            old(self).page_closure().contains(target_entry.addr) == false,
            page_ptr_valid(target_entry.addr),
        ensures
            self.wf(),
            self.kernel_l4_end == old(self).kernel_l4_end,
            self.page_closure() =~= old(self).page_closure(),
            self.mapping_4k@ == old(self).mapping_4k@.insert(
                spec_index2va((target_l4i, target_l3i, target_l2i, target_l1i)),
                *target_entry,
            ),
            self.mapping_2m() =~= old(self).mapping_2m(),
            self.mapping_1g() =~= old(self).mapping_1g(),
            self.kernel_entries =~= old(self).kernel_entries,
    {
        broadcast use PageTable::reveal_page_table_wf;
        broadcast use PageTable::reveal_page_table_levels_wf;
        // broadcast use PageTable::reveal_page_table_disjoint_wf;
        // broadcast use PageTable::reveal_page_table_mappings_wf;
        // broadcast use PageTable::reveal_page_table_addtional_wf;

        assert(va_4k_valid(spec_index2va((target_l4i, target_l3i, target_l2i, target_l1i)))) by {
            va_lemma();
        };
        assert(self.mapping_4k@.dom().contains(
            spec_index2va((target_l4i, target_l3i, target_l2i, target_l1i)),
        ) == false) by {
            broadcast use PageTable::reveal_page_table_mappings_wf;
        };
        let tracked mut l1_perm = self.l1_tables.borrow_mut().tracked_remove(target_l1_p);
        proof {
            page_ptr_valid_imply_MEM_valid(target_entry.addr);
        }
        page_map_set(
            target_l1_p,
            Tracked(&mut l1_perm),
            target_l1i,
            PageEntry {
                addr: target_entry.addr,
                perm: PageEntryPerm {
                    present: true,
                    ps: false,
                    write: target_entry.write,
                    execute_disable: target_entry.execute_disable,
                    user: true,
                },
            },
        );
        proof {
            self.l1_tables.borrow_mut().tracked_insert(target_l1_p, l1_perm);
            assert(self.spec_resolve_mapping_4k_l1(
                target_l4i,
                target_l3i,
                target_l2i,
                target_l1i,
            ).is_Some());
            self.mapping_4k@ = self.mapping_4k@.insert(
                spec_index2va((target_l4i, target_l3i, target_l2i, target_l1i)),
                *target_entry,
            );
        }
        assert(self.wf_l4());
        assert(self.wf_l3());
        assert(self.wf_l2());
        assert(self.wf_l1());
        assert(self.disjoint_l4()) by { broadcast use PageTable::reveal_page_table_disjoint_wf; };
        assert(self.disjoint_l3()) by { broadcast use PageTable::reveal_page_table_disjoint_wf; };
        assert(self.disjoint_l2()) by { broadcast use PageTable::reveal_page_table_disjoint_wf; };
        assert(self.disjoint_wf()) by { broadcast use PageTable::reveal_page_table_disjoint_wf; };
        assert(self.wf_mapping_4k()) by {
            broadcast use PageTable::reveal_page_table_mappings_wf;
            va_lemma();
            assert(forall|l4i: L4Index, l3i: L3Index, l2i: L2Index, l1i: L2Index|
                #![trigger self.mapping_4k@.dom().contains(spec_index2va((l4i,l3i,l2i,l1i)))]
                #![trigger old(self).mapping_4k@.dom().contains(spec_index2va((l4i,l3i,l2i,l1i)))]
                self.kernel_l4_end <= l4i < 512 && 0 <= l3i < 512 && 0 <= l2i < 512 && 0 <= l1i
                    < 512 && !((target_l4i, target_l3i, target_l2i, target_l1i) =~= (
                    l4i,
                    l3i,
                    l2i,
                    l1i,
                )) ==> self.mapping_4k@.dom().contains(spec_index2va((l4i, l3i, l2i, l1i))) == old(
                    self,
                ).mapping_4k@.dom().contains(spec_index2va((l4i, l3i, l2i, l1i))));

            assert(forall|l4i: L4Index, l3i: L3Index, l2i: L2Index|
                #![trigger self.spec_resolve_mapping_l2(l4i,l3i,l2i)]
                #![trigger old(self).spec_resolve_mapping_l2(l4i,l3i,l2i)]
                self.kernel_l4_end <= l4i < 512 && 0 <= l3i < 512 && 0 <= l2i < 512 && !((
                    target_l4i,
                    target_l3i,
                    target_l2i,
                ) =~= (l4i, l3i, l2i)) ==> self.spec_resolve_mapping_l2(l4i, l3i, l2i) =~= old(
                    self,
                ).spec_resolve_mapping_l2(l4i, l3i, l2i));

            assert(forall|l4i: L4Index, l3i: L3Index, l2i: L2Index|
                #![trigger self.spec_resolve_mapping_l2(l4i,l3i,l2i)]
                self.kernel_l4_end <= l4i < 512 && 0 <= l3i < 512 && 0 <= l2i < 512
                    && self.spec_resolve_mapping_l2(l4i, l3i, l2i).is_Some() && !((
                    target_l4i,
                    target_l3i,
                    target_l2i,
                ) =~= (l4i, l3i, l2i)) ==> self.spec_resolve_mapping_l2(
                    l4i,
                    l3i,
                    l2i,
                ).get_Some_0().addr != target_l1_p) by {
                old(self).internal_resolve_disjoint();
            };

            assert(forall|l4i: L4Index, l3i: L3Index, l2i: L2Index, l1i: L2Index|
                #![trigger self.spec_resolve_mapping_4k_l1(l4i,l3i,l2i,l1i)]
                #![trigger old(self).spec_resolve_mapping_4k_l1(l4i,l3i,l2i,l1i)]
                self.kernel_l4_end <= l4i < 512 && 0 <= l3i < 512 && 0 <= l2i < 512 && 0 <= l1i
                    < 512 && !((target_l4i, target_l3i, target_l2i) =~= (l4i, l3i, l2i))
                    ==> self.spec_resolve_mapping_4k_l1(l4i, l3i, l2i, l1i).is_Some() == old(
                    self,
                ).spec_resolve_mapping_4k_l1(l4i, l3i, l2i, l1i).is_Some());
        };
        assert(self.wf_mapping_2m()) by {
            broadcast use PageTable::reveal_page_table_mappings_wf;
            assert(forall|l4i: L4Index, l3i: L3Index, l2i: L2Index|
                #![trigger self.spec_resolve_mapping_2m_l2(l4i,l3i,l2i)]
                #![trigger old(self).spec_resolve_mapping_2m_l2(l4i,l3i,l2i)]
                self.kernel_l4_end <= l4i < 512 && 0 <= l3i < 512 && 0 <= l2i < 512 ==> old(
                    self,
                ).spec_resolve_mapping_2m_l2(l4i, l3i, l2i) == self.spec_resolve_mapping_2m_l2(
                    l4i,
                    l3i,
                    l2i,
                ));
        };
        assert(self.wf_mapping_1g()) by {
            broadcast use PageTable::reveal_page_table_mappings_wf;
            assert(forall|l4i: L4Index, l3i: L3Index|
                #![trigger self.spec_resolve_mapping_1g_l3(l4i,l3i)]
                #![trigger old(self).spec_resolve_mapping_1g_l3(l4i,l3i)]
                self.kernel_l4_end <= l4i < 512 && 0 <= l3i < 512 && (l4i, l3i) != (
                    target_l4i,
                    target_l3i,
                ) ==> old(self).spec_resolve_mapping_1g_l3(l4i, l3i)
                    =~= self.spec_resolve_mapping_1g_l3(l4i, l3i));
        };
        assert(self.mappings_wf()) by { broadcast use PageTable::reveal_page_table_mappings_wf; };
        // assert(self.user_only()) by {
        //     broadcast use PageTable::reveal_page_table_addtional_wf;
        // };
        // assert(self.rwx_upper_level_entries()) by {
        //     broadcast use PageTable::reveal_page_table_addtional_wf;
        // };
        // assert(self.present_or_zero()) by {
        //     broadcast use PageTable::reveal_page_table_addtional_wf;
        // };
        // assert(self.table_pages_wf()) by {
        //     broadcast use PageTable::reveal_page_table_addtional_wf;
        // };
        // assert(self.kernel_entries_wf()) by {
        //     broadcast use PageTable::reveal_page_table_addtional_wf;
        // }; 
        // assert(self.pcid_ioid_wf()) by {
        //     broadcast use PageTable::reveal_page_table_addtional_wf;
        // }; 
        // assert(self.tlb_wf()) by {
        //     broadcast use PageTable::reveal_page_table_addtional_wf;
        // }; 
        // assert(self.tlb_submap_of_mapping()) by {
        //     broadcast use PageTable::reveal_page_table_addtional_wf;
        // };
        assert(self.additonal_wf()) by {broadcast use PageTable::reveal_page_table_addtional_wf;}
        // assert(self.mapping_2m() =~= old(self).mapping_2m());
        // assert(self.mapping_1g() =~= old(self).mapping_1g());
    }

}



// File: lemma/lemma_u.rs
	#[verifier::external_body]
    #[verifier::spinoff_prover]
pub proof fn page_ptr_valid_imply_MEM_valid(v: usize)
    requires
        page_ptr_valid(v),
    ensures
        MEM_valid(v),
	{
		unimplemented!()
	}


// File: util/page_ptr_util_u.rs
pub open spec fn MEM_valid(v: PAddr) -> bool {
    v & (!MEM_MASK) as usize == 0
}

pub open spec fn page_ptr_valid(ptr: usize) -> bool {
    &&& ptr % 0x1000 == 0
    &&& ptr / 0x1000 < NUM_PAGES
}

pub open spec fn page_ptr_2m_valid(ptr: usize) -> bool {
    ((ptr % (0x200000)) == 0) && ((ptr / 4096) < NUM_PAGES)
}

pub open spec fn page_ptr_1g_valid(ptr: usize) -> bool {
    ((ptr % (0x40000000)) == 0) && ((ptr / 4096) < NUM_PAGES)
}

pub open spec fn spec_va_4k_valid(va: usize) -> bool {
    (va & (!MEM_4k_MASK) as usize == 0) && (va as u64 >> 39u64 & 0x1ffu64)
        >= KERNEL_MEM_END_L4INDEX as u64
}

#[verifier::external_body]
#[verifier(when_used_as_spec(spec_va_4k_valid))]
pub fn va_4k_valid(va: usize) -> (ret: bool)
    ensures
        ret == spec_va_4k_valid(va),
{
    unimplemented!()
}

pub open spec fn spec_va_2m_valid(va: usize) -> bool {
    (va & (!MEM_2m_MASK) as usize == 0) && (va as u64 >> 39u64 & 0x1ffu64)
        >= KERNEL_MEM_END_L4INDEX as u64
}

#[verifier::external_body]
#[verifier(when_used_as_spec(spec_va_2m_valid))]
pub fn va_2m_valid(va: usize) -> (ret: bool)
    ensures
        ret == spec_va_2m_valid(va),
{
    unimplemented!()
}

#[verifier::external_body]
#[verifier(when_used_as_spec(spec_va_2m_valid))]
pub fn va_1g_valid(va: usize) -> (ret: bool)
    ensures
        ret == spec_va_1g_valid(va),
{
    unimplemented!()
}

pub open spec fn spec_va_1g_valid(va: usize) -> bool {
    (va & (!MEM_1g_MASK) as usize == 0) && (va as u64 >> 39u64 & 0x1ffu64)
        >= KERNEL_MEM_END_L4INDEX as u64
}


pub open spec fn spec_v2l1index(va: usize) -> L1Index {
    (va >> 12 & 0x1ff) as usize
}

pub open spec fn spec_v2l2index(va: usize) -> L2Index {
    (va >> 21 & 0x1ff) as usize
}

pub open spec fn spec_v2l3index(va: usize) -> L3Index {
    (va >> 30 & 0x1ff) as usize
}

pub open spec fn spec_v2l4index(va: usize) -> L4Index {
    (va >> 39 & 0x1ff) as usize
}

pub open spec fn spec_va2index(va: usize) -> (L4Index, L3Index, L2Index, L1Index) {
    (spec_v2l4index(va), spec_v2l3index(va), spec_v2l2index(va), spec_v2l1index(va))
}

pub open spec fn spec_index2va(i: (L4Index, L3Index, L2Index, L1Index)) -> usize
    recommends
        i.0 <= 0x1ff,
        i.1 <= 0x1ff,
        i.2 <= 0x1ff,
        i.3 <= 0x1ff,
{
    (i.0 as usize) << 39 & (i.1 as usize) << 30 & (i.2 as usize) << 21 & (i.3 as usize) << 12
}

	#[verifier::external_body]
#[verifier(external_body)]
pub proof fn va_lemma()
    ensures
        forall|va: VAddr|
            #![trigger spec_va_4k_valid(va), spec_v2l4index(va)]
            #![trigger spec_va_4k_valid(va), spec_v2l3index(va)]
            #![trigger spec_va_4k_valid(va), spec_v2l2index(va)]
            #![trigger spec_va_4k_valid(va), spec_v2l1index(va)]
            spec_va_4k_valid(va) ==> 0 <= spec_v2l4index(va) < 512 && 0 <= spec_v2l3index(va) < 512
                && 0 <= spec_v2l2index(va) < 512 && 0 <= spec_v2l1index(va) < 512,
        forall|va: VAddr|
            #![trigger spec_va_2m_valid(va), spec_v2l4index(va)]
            #![trigger spec_va_2m_valid(va), spec_v2l3index(va)]
            #![trigger spec_va_2m_valid(va), spec_v2l2index(va)]
            #![trigger spec_va_2m_valid(va), spec_v2l1index(va)]
            spec_va_2m_valid(va) ==> 0 <= spec_v2l4index(va) < 512 && 0 <= spec_v2l3index(va) < 512
                && 0 <= spec_v2l2index(va) < 512 && 0 == spec_v2l1index(va),
        forall|va: VAddr|
            #![trigger spec_va_1g_valid(va), spec_v2l4index(va)]
            #![trigger spec_va_1g_valid(va), spec_v2l3index(va)]
            #![trigger spec_va_1g_valid(va), spec_v2l2index(va)]
            #![trigger spec_va_1g_valid(va), spec_v2l1index(va)]
            spec_va_1g_valid(va) ==> 0 <= spec_v2l4index(va) < 512 && 0 <= spec_v2l3index(va) < 512
                && 0 == spec_v2l2index(va) && 0 == spec_v2l1index(va),
        forall|
            l4i: L4Index,
            l3i: L3Index,
            l2i: L2Index,
            l1i: L1Index,
            l4j: L4Index,
            l3j: L3Index,
            l2j: L2Index,
            l1j: L1Index,
        |
            #![trigger spec_index2va((l4i,l3i,l2i,l1i)), spec_index2va((l4j,l3j,l2j,l1j))]
            (l4i, l3i, l2i, l1i) =~= (l4j, l3j, l2j, l1j) && 0 <= l4i < 512 && 0 <= l3i < 512 && 0
                <= l2i < 512 && 0 <= l1i < 512 && 0 <= l4j < 512 && 0 <= l3j < 512 && 0 <= l2j < 512
                && 0 <= l1j < 512 <==> spec_index2va((l4i, l3i, l2i, l1i)) == spec_index2va(
                (l4j, l3j, l2j, l1j),
            ),
        forall|
            l4i: L4Index,
            l3i: L3Index,
            l2i: L2Index,
            l1i: L1Index,
            l4j: L4Index,
            l3j: L3Index,
            l2j: L2Index,
            l1j: L1Index,
        |
            #![trigger spec_index2va((l4i,l3i,l2i,l1i)), spec_index2va((l4j,l3j,l2j,l1j))]
            (l4i, l3i, l2i, l1i) =~= (l4j, l3j, l2j, l1j) == false && 0 <= l4i < 512 && 0 <= l3i
                < 512 && 0 <= l2i < 512 && 0 <= l1i < 512 && 0 <= l4j < 512 && 0 <= l3j < 512 && 0
                <= l2j < 512 && 0 <= l1j < 512 <==> spec_index2va((l4i, l3i, l2i, l1i))
                != spec_index2va((l4j, l3j, l2j, l1j)),
        forall|l4i: L4Index, l3i: L3Index, l2i: L2Index, l1i: L1Index|
            #![trigger va_4k_valid(spec_index2va((l4i,l3i,l2i,l1i)))]
            0 <= l4i < 512 && 0 <= l3i < 512 && 0 <= l2i < 512 && 0 <= l1i < 512 ==> va_4k_valid(
                spec_index2va((l4i, l3i, l2i, l1i)),
            ),
        forall|va: VAddr, l4i: L4Index, l3i: L3Index, l2i: L2Index, l1i: L1Index|
            #![trigger spec_index2va((l4i,l3i,l2i,l1i)), spec_va2index(va)]
            va_4k_valid(va) && spec_va2index(va) == (l4i, l3i, l2i, l1i) <==> KERNEL_MEM_END_L4INDEX
                <= l4i < 512 && 0 <= l3i < 512 && 0 <= l2i < 512 && 0 <= l1i < 512 && spec_index2va(
                (l4i, l3i, l2i, l1i),
            ) == va,
        forall|l4i: L4Index, l3i: L3Index, l2i: L2Index|
            #![trigger va_2m_valid(spec_index2va((l4i,l3i,l2i,0)))]
            0 <= l4i < 512 && 0 <= l3i < 512 && 0 <= l2i < 512 ==> va_2m_valid(
                spec_index2va((l4i, l3i, l2i, 0)),
            ),
	{
		unimplemented!()
	}


// File: define.rs
pub const KERNEL_MEM_END_L4INDEX: usize = 1;

pub const NUM_PAGES: usize = 2 * 1024 * 1024;

pub const MEM_MASK: u64 = 0x0000_ffff_ffff_f000;

pub const MEM_4k_MASK: u64 = 0x0000_ffff_ffff_f000;

pub const MEM_2m_MASK: u64 = 0x0000_ffff_ffe0_0000;

pub const MEM_1g_MASK: u64 = 0x0000_fffc_0000_0000;

pub const NUM_CPUS: usize = 32;

pub const PAGE_ENTRY_WRITE_SHIFT: u64 = 1;

pub const PAGE_ENTRY_USER_SHIFT: u64 = 2;

pub const PAGE_ENTRY_PS_SHIFT: u64 = 7;

pub const PAGE_ENTRY_EXECUTE_SHIFT: u64 = 63;

pub const PAGE_ENTRY_PRESENT_MASK: u64 = 0x1;

pub const PAGE_ENTRY_WRITE_MASK: u64 = 0x1u64 << PAGE_ENTRY_WRITE_SHIFT;

pub const PAGE_ENTRY_USER_MASK: u64 = 0x1u64 << PAGE_ENTRY_USER_SHIFT;

pub const PAGE_ENTRY_PS_MASK: u64 = 0x1u64 << PAGE_ENTRY_PS_SHIFT;

pub const PAGE_ENTRY_EXECUTE_MASK: u64 = 0x1u64 << PAGE_ENTRY_EXECUTE_SHIFT;



// === INJECTED DET CHECK ===
// L4-llm view declarations (generated, see view_registry cache)
pub struct PageTableView {
    pub cr3: PageMapPtr,
    pub pcid: Option<Pcid>,
    pub ioid: Option<IOid>,
    pub kernel_l4_end: usize,
    pub l3_rev_map: Map<PageMapPtr, L4Index>,
    pub l2_rev_map: Map<PageMapPtr, (L4Index, L3Index)>,
    pub l1_rev_map: Map<PageMapPtr, (L4Index, L3Index, L2Index)>,
    pub mapping_4k: Map<VAddr, MapEntry>,
    pub mapping_2m: Map<VAddr, MapEntry>,
    pub mapping_1g: Map<VAddr, MapEntry>,
    pub kernel_entries: Seq<PageEntry>,
    pub tlb_mapping_4k: Seq<Map<VAddr, MapEntry>>,
    pub tlb_mapping_2m: Seq<Map<VAddr, MapEntry>>,
    pub tlb_mapping_1g: Seq<Map<VAddr, MapEntry>>,
}

impl View for PageTable {
    type V = PageTableView;
    closed spec fn view(&self) -> PageTableView {
        PageTableView {
            cr3: self.cr3,
            pcid: self.pcid,
            ioid: self.ioid,
            kernel_l4_end: self.kernel_l4_end,
            l3_rev_map: self.l3_rev_map@,
            l2_rev_map: self.l2_rev_map@,
            l1_rev_map: self.l1_rev_map@,
            mapping_4k: self.mapping_4k@,
            mapping_2m: self.mapping_2m@,
            mapping_1g: self.mapping_1g@,
            kernel_entries: self.kernel_entries@,
            tlb_mapping_4k: self.tlb_mapping_4k@,
            tlb_mapping_2m: self.tlb_mapping_2m@,
            tlb_mapping_1g: self.tlb_mapping_1g@,
        }
    }
}

// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_map_4k_page_equal(r1: (), r2: (), post1_self_: PageTable, post2_self_: PageTable) -> bool {
    (r1 == r2)
    && (((post1_self_).view() == (post2_self_).view()))
}

proof fn det_map_4k_page(g_pre_self__pcid_is_Some: bool, g_pre_self__pcid_is_None: bool, g_pre_self__ioid_is_Some: bool, g_pre_self__ioid_is_None: bool, g_pre_self__kernel_l4_end_eq: bool, k_pre_self__kernel_l4_end_eq: int, g_pre_self__kernel_l4_end_rng: bool, k_pre_self__kernel_l4_end_rng_lo: int, k_pre_self__kernel_l4_end_rng_hi: int, g__pre_self__l4_table___dom___empty: bool, g__pre_self__l4_table___dom___lengt: bool, g__pre_self__l4_table___dom___leneq: bool, k__pre_self__l4_table___dom___leneq: nat, g__pre_self__l4_table___dom___lenrng: bool, k__pre_self__l4_table___dom___lenrng_lo: nat, k__pre_self__l4_table___dom___lenrng_hi: nat, g__pre_self__l4_table___dom___contains: bool, k__pre_self__l4_table___dom___contains: PageMapPtr, g__pre_self__l3_rev_map___dom___empty: bool, g__pre_self__l3_rev_map___dom___lengt: bool, g__pre_self__l3_rev_map___dom___leneq: bool, k__pre_self__l3_rev_map___dom___leneq: nat, g__pre_self__l3_rev_map___dom___lenrng: bool, k__pre_self__l3_rev_map___dom___lenrng_lo: nat, k__pre_self__l3_rev_map___dom___lenrng_hi: nat, g__pre_self__l3_rev_map___dom___contains: bool, k__pre_self__l3_rev_map___dom___contains: PageMapPtr, g__pre_self__l3_tables___dom___empty: bool, g__pre_self__l3_tables___dom___lengt: bool, g__pre_self__l3_tables___dom___leneq: bool, k__pre_self__l3_tables___dom___leneq: nat, g__pre_self__l3_tables___dom___lenrng: bool, k__pre_self__l3_tables___dom___lenrng_lo: nat, k__pre_self__l3_tables___dom___lenrng_hi: nat, g__pre_self__l3_tables___dom___contains: bool, k__pre_self__l3_tables___dom___contains: PageMapPtr, g__pre_self__l2_rev_map___dom___empty: bool, g__pre_self__l2_rev_map___dom___lengt: bool, g__pre_self__l2_rev_map___dom___leneq: bool, k__pre_self__l2_rev_map___dom___leneq: nat, g__pre_self__l2_rev_map___dom___lenrng: bool, k__pre_self__l2_rev_map___dom___lenrng_lo: nat, k__pre_self__l2_rev_map___dom___lenrng_hi: nat, g__pre_self__l2_rev_map___dom___contains: bool, k__pre_self__l2_rev_map___dom___contains: PageMapPtr, g__pre_self__l2_tables___dom___empty: bool, g__pre_self__l2_tables___dom___lengt: bool, g__pre_self__l2_tables___dom___leneq: bool, k__pre_self__l2_tables___dom___leneq: nat, g__pre_self__l2_tables___dom___lenrng: bool, k__pre_self__l2_tables___dom___lenrng_lo: nat, k__pre_self__l2_tables___dom___lenrng_hi: nat, g__pre_self__l2_tables___dom___contains: bool, k__pre_self__l2_tables___dom___contains: PageMapPtr, g__pre_self__l1_rev_map___dom___empty: bool, g__pre_self__l1_rev_map___dom___lengt: bool, g__pre_self__l1_rev_map___dom___leneq: bool, k__pre_self__l1_rev_map___dom___leneq: nat, g__pre_self__l1_rev_map___dom___lenrng: bool, k__pre_self__l1_rev_map___dom___lenrng_lo: nat, k__pre_self__l1_rev_map___dom___lenrng_hi: nat, g__pre_self__l1_rev_map___dom___contains: bool, k__pre_self__l1_rev_map___dom___contains: PageMapPtr, g__pre_self__l1_tables___dom___empty: bool, g__pre_self__l1_tables___dom___lengt: bool, g__pre_self__l1_tables___dom___leneq: bool, k__pre_self__l1_tables___dom___leneq: nat, g__pre_self__l1_tables___dom___lenrng: bool, k__pre_self__l1_tables___dom___lenrng_lo: nat, k__pre_self__l1_tables___dom___lenrng_hi: nat, g__pre_self__l1_tables___dom___contains: bool, k__pre_self__l1_tables___dom___contains: PageMapPtr, g__pre_self__mapping_4k___dom___empty: bool, g__pre_self__mapping_4k___dom___lengt: bool, g__pre_self__mapping_4k___dom___leneq: bool, k__pre_self__mapping_4k___dom___leneq: nat, g__pre_self__mapping_4k___dom___lenrng: bool, k__pre_self__mapping_4k___dom___lenrng_lo: nat, k__pre_self__mapping_4k___dom___lenrng_hi: nat, g__pre_self__mapping_4k___dom___contains: bool, k__pre_self__mapping_4k___dom___contains: VAddr, g__pre_self__mapping_2m___dom___empty: bool, g__pre_self__mapping_2m___dom___lengt: bool, g__pre_self__mapping_2m___dom___leneq: bool, k__pre_self__mapping_2m___dom___leneq: nat, g__pre_self__mapping_2m___dom___lenrng: bool, k__pre_self__mapping_2m___dom___lenrng_lo: nat, k__pre_self__mapping_2m___dom___lenrng_hi: nat, g__pre_self__mapping_2m___dom___contains: bool, k__pre_self__mapping_2m___dom___contains: VAddr, g__pre_self__mapping_1g___dom___empty: bool, g__pre_self__mapping_1g___dom___lengt: bool, g__pre_self__mapping_1g___dom___leneq: bool, k__pre_self__mapping_1g___dom___leneq: nat, g__pre_self__mapping_1g___dom___lenrng: bool, k__pre_self__mapping_1g___dom___lenrng_lo: nat, k__pre_self__mapping_1g___dom___lenrng_hi: nat, g__pre_self__mapping_1g___dom___contains: bool, k__pre_self__mapping_1g___dom___contains: VAddr, g__pre_self__kernel_entries___leneq: bool, k__pre_self__kernel_entries___leneq: nat, g__pre_self__kernel_entries___lenrng: bool, k__pre_self__kernel_entries___lenrng_lo: nat, k__pre_self__kernel_entries___lenrng_hi: nat, g__pre_self__kernel_entries___0__perm_present_is_true: bool, g__pre_self__kernel_entries___0__perm_present_is_false: bool, g__pre_self__kernel_entries___0__perm_ps_is_true: bool, g__pre_self__kernel_entries___0__perm_ps_is_false: bool, g__pre_self__kernel_entries___0__perm_write_is_true: bool, g__pre_self__kernel_entries___0__perm_write_is_false: bool, g__pre_self__kernel_entries___0__perm_execute_disable_is_true: bool, g__pre_self__kernel_entries___0__perm_execute_disable_is_false: bool, g__pre_self__kernel_entries___0__perm_user_is_true: bool, g__pre_self__kernel_entries___0__perm_user_is_false: bool, g__pre_self__kernel_entries___1__perm_present_is_true: bool, g__pre_self__kernel_entries___1__perm_present_is_false: bool, g__pre_self__kernel_entries___1__perm_ps_is_true: bool, g__pre_self__kernel_entries___1__perm_ps_is_false: bool, g__pre_self__kernel_entries___1__perm_write_is_true: bool, g__pre_self__kernel_entries___1__perm_write_is_false: bool, g__pre_self__kernel_entries___1__perm_execute_disable_is_true: bool, g__pre_self__kernel_entries___1__perm_execute_disable_is_false: bool, g__pre_self__kernel_entries___1__perm_user_is_true: bool, g__pre_self__kernel_entries___1__perm_user_is_false: bool, g__pre_self__kernel_entries___2__perm_present_is_true: bool, g__pre_self__kernel_entries___2__perm_present_is_false: bool, g__pre_self__kernel_entries___2__perm_ps_is_true: bool, g__pre_self__kernel_entries___2__perm_ps_is_false: bool, g__pre_self__kernel_entries___2__perm_write_is_true: bool, g__pre_self__kernel_entries___2__perm_write_is_false: bool, g__pre_self__kernel_entries___2__perm_execute_disable_is_true: bool, g__pre_self__kernel_entries___2__perm_execute_disable_is_false: bool, g__pre_self__kernel_entries___2__perm_user_is_true: bool, g__pre_self__kernel_entries___2__perm_user_is_false: bool, g__pre_self__kernel_entries___3__perm_present_is_true: bool, g__pre_self__kernel_entries___3__perm_present_is_false: bool, g__pre_self__kernel_entries___3__perm_ps_is_true: bool, g__pre_self__kernel_entries___3__perm_ps_is_false: bool, g__pre_self__kernel_entries___3__perm_write_is_true: bool, g__pre_self__kernel_entries___3__perm_write_is_false: bool, g__pre_self__kernel_entries___3__perm_execute_disable_is_true: bool, g__pre_self__kernel_entries___3__perm_execute_disable_is_false: bool, g__pre_self__kernel_entries___3__perm_user_is_true: bool, g__pre_self__kernel_entries___3__perm_user_is_false: bool, g__pre_self__kernel_entries___4__perm_present_is_true: bool, g__pre_self__kernel_entries___4__perm_present_is_false: bool, g__pre_self__kernel_entries___4__perm_ps_is_true: bool, g__pre_self__kernel_entries___4__perm_ps_is_false: bool, g__pre_self__kernel_entries___4__perm_write_is_true: bool, g__pre_self__kernel_entries___4__perm_write_is_false: bool, g__pre_self__kernel_entries___4__perm_execute_disable_is_true: bool, g__pre_self__kernel_entries___4__perm_execute_disable_is_false: bool, g__pre_self__kernel_entries___4__perm_user_is_true: bool, g__pre_self__kernel_entries___4__perm_user_is_false: bool, g__pre_self__kernel_entries___5__perm_present_is_true: bool, g__pre_self__kernel_entries___5__perm_present_is_false: bool, g__pre_self__kernel_entries___5__perm_ps_is_true: bool, g__pre_self__kernel_entries___5__perm_ps_is_false: bool, g__pre_self__kernel_entries___5__perm_write_is_true: bool, g__pre_self__kernel_entries___5__perm_write_is_false: bool, g__pre_self__kernel_entries___5__perm_execute_disable_is_true: bool, g__pre_self__kernel_entries___5__perm_execute_disable_is_false: bool, g__pre_self__kernel_entries___5__perm_user_is_true: bool, g__pre_self__kernel_entries___5__perm_user_is_false: bool, g__pre_self__kernel_entries___6__perm_present_is_true: bool, g__pre_self__kernel_entries___6__perm_present_is_false: bool, g__pre_self__kernel_entries___6__perm_ps_is_true: bool, g__pre_self__kernel_entries___6__perm_ps_is_false: bool, g__pre_self__kernel_entries___6__perm_write_is_true: bool, g__pre_self__kernel_entries___6__perm_write_is_false: bool, g__pre_self__kernel_entries___6__perm_execute_disable_is_true: bool, g__pre_self__kernel_entries___6__perm_execute_disable_is_false: bool, g__pre_self__kernel_entries___6__perm_user_is_true: bool, g__pre_self__kernel_entries___6__perm_user_is_false: bool, g__pre_self__kernel_entries___7__perm_present_is_true: bool, g__pre_self__kernel_entries___7__perm_present_is_false: bool, g__pre_self__kernel_entries___7__perm_ps_is_true: bool, g__pre_self__kernel_entries___7__perm_ps_is_false: bool, g__pre_self__kernel_entries___7__perm_write_is_true: bool, g__pre_self__kernel_entries___7__perm_write_is_false: bool, g__pre_self__kernel_entries___7__perm_execute_disable_is_true: bool, g__pre_self__kernel_entries___7__perm_execute_disable_is_false: bool, g__pre_self__kernel_entries___7__perm_user_is_true: bool, g__pre_self__kernel_entries___7__perm_user_is_false: bool, g__pre_self__tlb_mapping_4k___leneq: bool, k__pre_self__tlb_mapping_4k___leneq: nat, g__pre_self__tlb_mapping_4k___lenrng: bool, k__pre_self__tlb_mapping_4k___lenrng_lo: nat, k__pre_self__tlb_mapping_4k___lenrng_hi: nat, g__pre_self__tlb_mapping_4k___0__dom___empty: bool, g__pre_self__tlb_mapping_4k___0__dom___lengt: bool, g__pre_self__tlb_mapping_4k___0__dom___leneq: bool, k__pre_self__tlb_mapping_4k___0__dom___leneq: nat, g__pre_self__tlb_mapping_4k___0__dom___lenrng: bool, k__pre_self__tlb_mapping_4k___0__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_4k___0__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_4k___0__dom___contains: bool, k__pre_self__tlb_mapping_4k___0__dom___contains: VAddr, g__pre_self__tlb_mapping_4k___1__dom___empty: bool, g__pre_self__tlb_mapping_4k___1__dom___lengt: bool, g__pre_self__tlb_mapping_4k___1__dom___leneq: bool, k__pre_self__tlb_mapping_4k___1__dom___leneq: nat, g__pre_self__tlb_mapping_4k___1__dom___lenrng: bool, k__pre_self__tlb_mapping_4k___1__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_4k___1__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_4k___1__dom___contains: bool, k__pre_self__tlb_mapping_4k___1__dom___contains: VAddr, g__pre_self__tlb_mapping_4k___2__dom___empty: bool, g__pre_self__tlb_mapping_4k___2__dom___lengt: bool, g__pre_self__tlb_mapping_4k___2__dom___leneq: bool, k__pre_self__tlb_mapping_4k___2__dom___leneq: nat, g__pre_self__tlb_mapping_4k___2__dom___lenrng: bool, k__pre_self__tlb_mapping_4k___2__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_4k___2__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_4k___2__dom___contains: bool, k__pre_self__tlb_mapping_4k___2__dom___contains: VAddr, g__pre_self__tlb_mapping_4k___3__dom___empty: bool, g__pre_self__tlb_mapping_4k___3__dom___lengt: bool, g__pre_self__tlb_mapping_4k___3__dom___leneq: bool, k__pre_self__tlb_mapping_4k___3__dom___leneq: nat, g__pre_self__tlb_mapping_4k___3__dom___lenrng: bool, k__pre_self__tlb_mapping_4k___3__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_4k___3__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_4k___3__dom___contains: bool, k__pre_self__tlb_mapping_4k___3__dom___contains: VAddr, g__pre_self__tlb_mapping_4k___4__dom___empty: bool, g__pre_self__tlb_mapping_4k___4__dom___lengt: bool, g__pre_self__tlb_mapping_4k___4__dom___leneq: bool, k__pre_self__tlb_mapping_4k___4__dom___leneq: nat, g__pre_self__tlb_mapping_4k___4__dom___lenrng: bool, k__pre_self__tlb_mapping_4k___4__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_4k___4__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_4k___4__dom___contains: bool, k__pre_self__tlb_mapping_4k___4__dom___contains: VAddr, g__pre_self__tlb_mapping_4k___5__dom___empty: bool, g__pre_self__tlb_mapping_4k___5__dom___lengt: bool, g__pre_self__tlb_mapping_4k___5__dom___leneq: bool, k__pre_self__tlb_mapping_4k___5__dom___leneq: nat, g__pre_self__tlb_mapping_4k___5__dom___lenrng: bool, k__pre_self__tlb_mapping_4k___5__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_4k___5__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_4k___5__dom___contains: bool, k__pre_self__tlb_mapping_4k___5__dom___contains: VAddr, g__pre_self__tlb_mapping_4k___6__dom___empty: bool, g__pre_self__tlb_mapping_4k___6__dom___lengt: bool, g__pre_self__tlb_mapping_4k___6__dom___leneq: bool, k__pre_self__tlb_mapping_4k___6__dom___leneq: nat, g__pre_self__tlb_mapping_4k___6__dom___lenrng: bool, k__pre_self__tlb_mapping_4k___6__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_4k___6__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_4k___6__dom___contains: bool, k__pre_self__tlb_mapping_4k___6__dom___contains: VAddr, g__pre_self__tlb_mapping_4k___7__dom___empty: bool, g__pre_self__tlb_mapping_4k___7__dom___lengt: bool, g__pre_self__tlb_mapping_4k___7__dom___leneq: bool, k__pre_self__tlb_mapping_4k___7__dom___leneq: nat, g__pre_self__tlb_mapping_4k___7__dom___lenrng: bool, k__pre_self__tlb_mapping_4k___7__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_4k___7__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_4k___7__dom___contains: bool, k__pre_self__tlb_mapping_4k___7__dom___contains: VAddr, g__pre_self__tlb_mapping_2m___leneq: bool, k__pre_self__tlb_mapping_2m___leneq: nat, g__pre_self__tlb_mapping_2m___lenrng: bool, k__pre_self__tlb_mapping_2m___lenrng_lo: nat, k__pre_self__tlb_mapping_2m___lenrng_hi: nat, g__pre_self__tlb_mapping_2m___0__dom___empty: bool, g__pre_self__tlb_mapping_2m___0__dom___lengt: bool, g__pre_self__tlb_mapping_2m___0__dom___leneq: bool, k__pre_self__tlb_mapping_2m___0__dom___leneq: nat, g__pre_self__tlb_mapping_2m___0__dom___lenrng: bool, k__pre_self__tlb_mapping_2m___0__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_2m___0__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_2m___0__dom___contains: bool, k__pre_self__tlb_mapping_2m___0__dom___contains: VAddr, g__pre_self__tlb_mapping_2m___1__dom___empty: bool, g__pre_self__tlb_mapping_2m___1__dom___lengt: bool, g__pre_self__tlb_mapping_2m___1__dom___leneq: bool, k__pre_self__tlb_mapping_2m___1__dom___leneq: nat, g__pre_self__tlb_mapping_2m___1__dom___lenrng: bool, k__pre_self__tlb_mapping_2m___1__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_2m___1__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_2m___1__dom___contains: bool, k__pre_self__tlb_mapping_2m___1__dom___contains: VAddr, g__pre_self__tlb_mapping_2m___2__dom___empty: bool, g__pre_self__tlb_mapping_2m___2__dom___lengt: bool, g__pre_self__tlb_mapping_2m___2__dom___leneq: bool, k__pre_self__tlb_mapping_2m___2__dom___leneq: nat, g__pre_self__tlb_mapping_2m___2__dom___lenrng: bool, k__pre_self__tlb_mapping_2m___2__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_2m___2__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_2m___2__dom___contains: bool, k__pre_self__tlb_mapping_2m___2__dom___contains: VAddr, g__pre_self__tlb_mapping_2m___3__dom___empty: bool, g__pre_self__tlb_mapping_2m___3__dom___lengt: bool, g__pre_self__tlb_mapping_2m___3__dom___leneq: bool, k__pre_self__tlb_mapping_2m___3__dom___leneq: nat, g__pre_self__tlb_mapping_2m___3__dom___lenrng: bool, k__pre_self__tlb_mapping_2m___3__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_2m___3__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_2m___3__dom___contains: bool, k__pre_self__tlb_mapping_2m___3__dom___contains: VAddr, g__pre_self__tlb_mapping_2m___4__dom___empty: bool, g__pre_self__tlb_mapping_2m___4__dom___lengt: bool, g__pre_self__tlb_mapping_2m___4__dom___leneq: bool, k__pre_self__tlb_mapping_2m___4__dom___leneq: nat, g__pre_self__tlb_mapping_2m___4__dom___lenrng: bool, k__pre_self__tlb_mapping_2m___4__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_2m___4__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_2m___4__dom___contains: bool, k__pre_self__tlb_mapping_2m___4__dom___contains: VAddr, g__pre_self__tlb_mapping_2m___5__dom___empty: bool, g__pre_self__tlb_mapping_2m___5__dom___lengt: bool, g__pre_self__tlb_mapping_2m___5__dom___leneq: bool, k__pre_self__tlb_mapping_2m___5__dom___leneq: nat, g__pre_self__tlb_mapping_2m___5__dom___lenrng: bool, k__pre_self__tlb_mapping_2m___5__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_2m___5__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_2m___5__dom___contains: bool, k__pre_self__tlb_mapping_2m___5__dom___contains: VAddr, g__pre_self__tlb_mapping_2m___6__dom___empty: bool, g__pre_self__tlb_mapping_2m___6__dom___lengt: bool, g__pre_self__tlb_mapping_2m___6__dom___leneq: bool, k__pre_self__tlb_mapping_2m___6__dom___leneq: nat, g__pre_self__tlb_mapping_2m___6__dom___lenrng: bool, k__pre_self__tlb_mapping_2m___6__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_2m___6__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_2m___6__dom___contains: bool, k__pre_self__tlb_mapping_2m___6__dom___contains: VAddr, g__pre_self__tlb_mapping_2m___7__dom___empty: bool, g__pre_self__tlb_mapping_2m___7__dom___lengt: bool, g__pre_self__tlb_mapping_2m___7__dom___leneq: bool, k__pre_self__tlb_mapping_2m___7__dom___leneq: nat, g__pre_self__tlb_mapping_2m___7__dom___lenrng: bool, k__pre_self__tlb_mapping_2m___7__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_2m___7__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_2m___7__dom___contains: bool, k__pre_self__tlb_mapping_2m___7__dom___contains: VAddr, g__pre_self__tlb_mapping_1g___leneq: bool, k__pre_self__tlb_mapping_1g___leneq: nat, g__pre_self__tlb_mapping_1g___lenrng: bool, k__pre_self__tlb_mapping_1g___lenrng_lo: nat, k__pre_self__tlb_mapping_1g___lenrng_hi: nat, g__pre_self__tlb_mapping_1g___0__dom___empty: bool, g__pre_self__tlb_mapping_1g___0__dom___lengt: bool, g__pre_self__tlb_mapping_1g___0__dom___leneq: bool, k__pre_self__tlb_mapping_1g___0__dom___leneq: nat, g__pre_self__tlb_mapping_1g___0__dom___lenrng: bool, k__pre_self__tlb_mapping_1g___0__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_1g___0__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_1g___0__dom___contains: bool, k__pre_self__tlb_mapping_1g___0__dom___contains: VAddr, g__pre_self__tlb_mapping_1g___1__dom___empty: bool, g__pre_self__tlb_mapping_1g___1__dom___lengt: bool, g__pre_self__tlb_mapping_1g___1__dom___leneq: bool, k__pre_self__tlb_mapping_1g___1__dom___leneq: nat, g__pre_self__tlb_mapping_1g___1__dom___lenrng: bool, k__pre_self__tlb_mapping_1g___1__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_1g___1__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_1g___1__dom___contains: bool, k__pre_self__tlb_mapping_1g___1__dom___contains: VAddr, g__pre_self__tlb_mapping_1g___2__dom___empty: bool, g__pre_self__tlb_mapping_1g___2__dom___lengt: bool, g__pre_self__tlb_mapping_1g___2__dom___leneq: bool, k__pre_self__tlb_mapping_1g___2__dom___leneq: nat, g__pre_self__tlb_mapping_1g___2__dom___lenrng: bool, k__pre_self__tlb_mapping_1g___2__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_1g___2__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_1g___2__dom___contains: bool, k__pre_self__tlb_mapping_1g___2__dom___contains: VAddr, g__pre_self__tlb_mapping_1g___3__dom___empty: bool, g__pre_self__tlb_mapping_1g___3__dom___lengt: bool, g__pre_self__tlb_mapping_1g___3__dom___leneq: bool, k__pre_self__tlb_mapping_1g___3__dom___leneq: nat, g__pre_self__tlb_mapping_1g___3__dom___lenrng: bool, k__pre_self__tlb_mapping_1g___3__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_1g___3__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_1g___3__dom___contains: bool, k__pre_self__tlb_mapping_1g___3__dom___contains: VAddr, g__pre_self__tlb_mapping_1g___4__dom___empty: bool, g__pre_self__tlb_mapping_1g___4__dom___lengt: bool, g__pre_self__tlb_mapping_1g___4__dom___leneq: bool, k__pre_self__tlb_mapping_1g___4__dom___leneq: nat, g__pre_self__tlb_mapping_1g___4__dom___lenrng: bool, k__pre_self__tlb_mapping_1g___4__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_1g___4__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_1g___4__dom___contains: bool, k__pre_self__tlb_mapping_1g___4__dom___contains: VAddr, g__pre_self__tlb_mapping_1g___5__dom___empty: bool, g__pre_self__tlb_mapping_1g___5__dom___lengt: bool, g__pre_self__tlb_mapping_1g___5__dom___leneq: bool, k__pre_self__tlb_mapping_1g___5__dom___leneq: nat, g__pre_self__tlb_mapping_1g___5__dom___lenrng: bool, k__pre_self__tlb_mapping_1g___5__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_1g___5__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_1g___5__dom___contains: bool, k__pre_self__tlb_mapping_1g___5__dom___contains: VAddr, g__pre_self__tlb_mapping_1g___6__dom___empty: bool, g__pre_self__tlb_mapping_1g___6__dom___lengt: bool, g__pre_self__tlb_mapping_1g___6__dom___leneq: bool, k__pre_self__tlb_mapping_1g___6__dom___leneq: nat, g__pre_self__tlb_mapping_1g___6__dom___lenrng: bool, k__pre_self__tlb_mapping_1g___6__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_1g___6__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_1g___6__dom___contains: bool, k__pre_self__tlb_mapping_1g___6__dom___contains: VAddr, g__pre_self__tlb_mapping_1g___7__dom___empty: bool, g__pre_self__tlb_mapping_1g___7__dom___lengt: bool, g__pre_self__tlb_mapping_1g___7__dom___leneq: bool, k__pre_self__tlb_mapping_1g___7__dom___leneq: nat, g__pre_self__tlb_mapping_1g___7__dom___lenrng: bool, k__pre_self__tlb_mapping_1g___7__dom___lenrng_lo: nat, k__pre_self__tlb_mapping_1g___7__dom___lenrng_hi: nat, g__pre_self__tlb_mapping_1g___7__dom___contains: bool, k__pre_self__tlb_mapping_1g___7__dom___contains: VAddr, g_target_entry_write_is_true: bool, g_target_entry_write_is_false: bool, g_target_entry_execute_disable_is_true: bool, g_target_entry_execute_disable_is_false: bool, g_post1_self__pcid_is_Some: bool, g_post1_self__pcid_is_None: bool, g_post1_self__ioid_is_Some: bool, g_post1_self__ioid_is_None: bool, g_post1_self__kernel_l4_end_eq: bool, k_post1_self__kernel_l4_end_eq: int, g_post1_self__kernel_l4_end_rng: bool, k_post1_self__kernel_l4_end_rng_lo: int, k_post1_self__kernel_l4_end_rng_hi: int, g__post1_self__l4_table___dom___empty: bool, g__post1_self__l4_table___dom___lengt: bool, g__post1_self__l4_table___dom___leneq: bool, k__post1_self__l4_table___dom___leneq: nat, g__post1_self__l4_table___dom___lenrng: bool, k__post1_self__l4_table___dom___lenrng_lo: nat, k__post1_self__l4_table___dom___lenrng_hi: nat, g__post1_self__l4_table___dom___contains: bool, k__post1_self__l4_table___dom___contains: PageMapPtr, g__post1_self__l3_rev_map___dom___empty: bool, g__post1_self__l3_rev_map___dom___lengt: bool, g__post1_self__l3_rev_map___dom___leneq: bool, k__post1_self__l3_rev_map___dom___leneq: nat, g__post1_self__l3_rev_map___dom___lenrng: bool, k__post1_self__l3_rev_map___dom___lenrng_lo: nat, k__post1_self__l3_rev_map___dom___lenrng_hi: nat, g__post1_self__l3_rev_map___dom___contains: bool, k__post1_self__l3_rev_map___dom___contains: PageMapPtr, g__post1_self__l3_tables___dom___empty: bool, g__post1_self__l3_tables___dom___lengt: bool, g__post1_self__l3_tables___dom___leneq: bool, k__post1_self__l3_tables___dom___leneq: nat, g__post1_self__l3_tables___dom___lenrng: bool, k__post1_self__l3_tables___dom___lenrng_lo: nat, k__post1_self__l3_tables___dom___lenrng_hi: nat, g__post1_self__l3_tables___dom___contains: bool, k__post1_self__l3_tables___dom___contains: PageMapPtr, g__post1_self__l2_rev_map___dom___empty: bool, g__post1_self__l2_rev_map___dom___lengt: bool, g__post1_self__l2_rev_map___dom___leneq: bool, k__post1_self__l2_rev_map___dom___leneq: nat, g__post1_self__l2_rev_map___dom___lenrng: bool, k__post1_self__l2_rev_map___dom___lenrng_lo: nat, k__post1_self__l2_rev_map___dom___lenrng_hi: nat, g__post1_self__l2_rev_map___dom___contains: bool, k__post1_self__l2_rev_map___dom___contains: PageMapPtr, g__post1_self__l2_tables___dom___empty: bool, g__post1_self__l2_tables___dom___lengt: bool, g__post1_self__l2_tables___dom___leneq: bool, k__post1_self__l2_tables___dom___leneq: nat, g__post1_self__l2_tables___dom___lenrng: bool, k__post1_self__l2_tables___dom___lenrng_lo: nat, k__post1_self__l2_tables___dom___lenrng_hi: nat, g__post1_self__l2_tables___dom___contains: bool, k__post1_self__l2_tables___dom___contains: PageMapPtr, g__post1_self__l1_rev_map___dom___empty: bool, g__post1_self__l1_rev_map___dom___lengt: bool, g__post1_self__l1_rev_map___dom___leneq: bool, k__post1_self__l1_rev_map___dom___leneq: nat, g__post1_self__l1_rev_map___dom___lenrng: bool, k__post1_self__l1_rev_map___dom___lenrng_lo: nat, k__post1_self__l1_rev_map___dom___lenrng_hi: nat, g__post1_self__l1_rev_map___dom___contains: bool, k__post1_self__l1_rev_map___dom___contains: PageMapPtr, g__post1_self__l1_tables___dom___empty: bool, g__post1_self__l1_tables___dom___lengt: bool, g__post1_self__l1_tables___dom___leneq: bool, k__post1_self__l1_tables___dom___leneq: nat, g__post1_self__l1_tables___dom___lenrng: bool, k__post1_self__l1_tables___dom___lenrng_lo: nat, k__post1_self__l1_tables___dom___lenrng_hi: nat, g__post1_self__l1_tables___dom___contains: bool, k__post1_self__l1_tables___dom___contains: PageMapPtr, g__post1_self__mapping_4k___dom___empty: bool, g__post1_self__mapping_4k___dom___lengt: bool, g__post1_self__mapping_4k___dom___leneq: bool, k__post1_self__mapping_4k___dom___leneq: nat, g__post1_self__mapping_4k___dom___lenrng: bool, k__post1_self__mapping_4k___dom___lenrng_lo: nat, k__post1_self__mapping_4k___dom___lenrng_hi: nat, g__post1_self__mapping_4k___dom___contains: bool, k__post1_self__mapping_4k___dom___contains: VAddr, g__post1_self__mapping_2m___dom___empty: bool, g__post1_self__mapping_2m___dom___lengt: bool, g__post1_self__mapping_2m___dom___leneq: bool, k__post1_self__mapping_2m___dom___leneq: nat, g__post1_self__mapping_2m___dom___lenrng: bool, k__post1_self__mapping_2m___dom___lenrng_lo: nat, k__post1_self__mapping_2m___dom___lenrng_hi: nat, g__post1_self__mapping_2m___dom___contains: bool, k__post1_self__mapping_2m___dom___contains: VAddr, g__post1_self__mapping_1g___dom___empty: bool, g__post1_self__mapping_1g___dom___lengt: bool, g__post1_self__mapping_1g___dom___leneq: bool, k__post1_self__mapping_1g___dom___leneq: nat, g__post1_self__mapping_1g___dom___lenrng: bool, k__post1_self__mapping_1g___dom___lenrng_lo: nat, k__post1_self__mapping_1g___dom___lenrng_hi: nat, g__post1_self__mapping_1g___dom___contains: bool, k__post1_self__mapping_1g___dom___contains: VAddr, g__post1_self__kernel_entries___leneq: bool, k__post1_self__kernel_entries___leneq: nat, g__post1_self__kernel_entries___lenrng: bool, k__post1_self__kernel_entries___lenrng_lo: nat, k__post1_self__kernel_entries___lenrng_hi: nat, g__post1_self__kernel_entries___0__perm_present_is_true: bool, g__post1_self__kernel_entries___0__perm_present_is_false: bool, g__post1_self__kernel_entries___0__perm_ps_is_true: bool, g__post1_self__kernel_entries___0__perm_ps_is_false: bool, g__post1_self__kernel_entries___0__perm_write_is_true: bool, g__post1_self__kernel_entries___0__perm_write_is_false: bool, g__post1_self__kernel_entries___0__perm_execute_disable_is_true: bool, g__post1_self__kernel_entries___0__perm_execute_disable_is_false: bool, g__post1_self__kernel_entries___0__perm_user_is_true: bool, g__post1_self__kernel_entries___0__perm_user_is_false: bool, g__post1_self__kernel_entries___1__perm_present_is_true: bool, g__post1_self__kernel_entries___1__perm_present_is_false: bool, g__post1_self__kernel_entries___1__perm_ps_is_true: bool, g__post1_self__kernel_entries___1__perm_ps_is_false: bool, g__post1_self__kernel_entries___1__perm_write_is_true: bool, g__post1_self__kernel_entries___1__perm_write_is_false: bool, g__post1_self__kernel_entries___1__perm_execute_disable_is_true: bool, g__post1_self__kernel_entries___1__perm_execute_disable_is_false: bool, g__post1_self__kernel_entries___1__perm_user_is_true: bool, g__post1_self__kernel_entries___1__perm_user_is_false: bool, g__post1_self__kernel_entries___2__perm_present_is_true: bool, g__post1_self__kernel_entries___2__perm_present_is_false: bool, g__post1_self__kernel_entries___2__perm_ps_is_true: bool, g__post1_self__kernel_entries___2__perm_ps_is_false: bool, g__post1_self__kernel_entries___2__perm_write_is_true: bool, g__post1_self__kernel_entries___2__perm_write_is_false: bool, g__post1_self__kernel_entries___2__perm_execute_disable_is_true: bool, g__post1_self__kernel_entries___2__perm_execute_disable_is_false: bool, g__post1_self__kernel_entries___2__perm_user_is_true: bool, g__post1_self__kernel_entries___2__perm_user_is_false: bool, g__post1_self__kernel_entries___3__perm_present_is_true: bool, g__post1_self__kernel_entries___3__perm_present_is_false: bool, g__post1_self__kernel_entries___3__perm_ps_is_true: bool, g__post1_self__kernel_entries___3__perm_ps_is_false: bool, g__post1_self__kernel_entries___3__perm_write_is_true: bool, g__post1_self__kernel_entries___3__perm_write_is_false: bool, g__post1_self__kernel_entries___3__perm_execute_disable_is_true: bool, g__post1_self__kernel_entries___3__perm_execute_disable_is_false: bool, g__post1_self__kernel_entries___3__perm_user_is_true: bool, g__post1_self__kernel_entries___3__perm_user_is_false: bool, g__post1_self__kernel_entries___4__perm_present_is_true: bool, g__post1_self__kernel_entries___4__perm_present_is_false: bool, g__post1_self__kernel_entries___4__perm_ps_is_true: bool, g__post1_self__kernel_entries___4__perm_ps_is_false: bool, g__post1_self__kernel_entries___4__perm_write_is_true: bool, g__post1_self__kernel_entries___4__perm_write_is_false: bool, g__post1_self__kernel_entries___4__perm_execute_disable_is_true: bool, g__post1_self__kernel_entries___4__perm_execute_disable_is_false: bool, g__post1_self__kernel_entries___4__perm_user_is_true: bool, g__post1_self__kernel_entries___4__perm_user_is_false: bool, g__post1_self__kernel_entries___5__perm_present_is_true: bool, g__post1_self__kernel_entries___5__perm_present_is_false: bool, g__post1_self__kernel_entries___5__perm_ps_is_true: bool, g__post1_self__kernel_entries___5__perm_ps_is_false: bool, g__post1_self__kernel_entries___5__perm_write_is_true: bool, g__post1_self__kernel_entries___5__perm_write_is_false: bool, g__post1_self__kernel_entries___5__perm_execute_disable_is_true: bool, g__post1_self__kernel_entries___5__perm_execute_disable_is_false: bool, g__post1_self__kernel_entries___5__perm_user_is_true: bool, g__post1_self__kernel_entries___5__perm_user_is_false: bool, g__post1_self__kernel_entries___6__perm_present_is_true: bool, g__post1_self__kernel_entries___6__perm_present_is_false: bool, g__post1_self__kernel_entries___6__perm_ps_is_true: bool, g__post1_self__kernel_entries___6__perm_ps_is_false: bool, g__post1_self__kernel_entries___6__perm_write_is_true: bool, g__post1_self__kernel_entries___6__perm_write_is_false: bool, g__post1_self__kernel_entries___6__perm_execute_disable_is_true: bool, g__post1_self__kernel_entries___6__perm_execute_disable_is_false: bool, g__post1_self__kernel_entries___6__perm_user_is_true: bool, g__post1_self__kernel_entries___6__perm_user_is_false: bool, g__post1_self__kernel_entries___7__perm_present_is_true: bool, g__post1_self__kernel_entries___7__perm_present_is_false: bool, g__post1_self__kernel_entries___7__perm_ps_is_true: bool, g__post1_self__kernel_entries___7__perm_ps_is_false: bool, g__post1_self__kernel_entries___7__perm_write_is_true: bool, g__post1_self__kernel_entries___7__perm_write_is_false: bool, g__post1_self__kernel_entries___7__perm_execute_disable_is_true: bool, g__post1_self__kernel_entries___7__perm_execute_disable_is_false: bool, g__post1_self__kernel_entries___7__perm_user_is_true: bool, g__post1_self__kernel_entries___7__perm_user_is_false: bool, g__post1_self__tlb_mapping_4k___leneq: bool, k__post1_self__tlb_mapping_4k___leneq: nat, g__post1_self__tlb_mapping_4k___lenrng: bool, k__post1_self__tlb_mapping_4k___lenrng_lo: nat, k__post1_self__tlb_mapping_4k___lenrng_hi: nat, g__post1_self__tlb_mapping_4k___0__dom___empty: bool, g__post1_self__tlb_mapping_4k___0__dom___lengt: bool, g__post1_self__tlb_mapping_4k___0__dom___leneq: bool, k__post1_self__tlb_mapping_4k___0__dom___leneq: nat, g__post1_self__tlb_mapping_4k___0__dom___lenrng: bool, k__post1_self__tlb_mapping_4k___0__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_4k___0__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_4k___0__dom___contains: bool, k__post1_self__tlb_mapping_4k___0__dom___contains: VAddr, g__post1_self__tlb_mapping_4k___1__dom___empty: bool, g__post1_self__tlb_mapping_4k___1__dom___lengt: bool, g__post1_self__tlb_mapping_4k___1__dom___leneq: bool, k__post1_self__tlb_mapping_4k___1__dom___leneq: nat, g__post1_self__tlb_mapping_4k___1__dom___lenrng: bool, k__post1_self__tlb_mapping_4k___1__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_4k___1__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_4k___1__dom___contains: bool, k__post1_self__tlb_mapping_4k___1__dom___contains: VAddr, g__post1_self__tlb_mapping_4k___2__dom___empty: bool, g__post1_self__tlb_mapping_4k___2__dom___lengt: bool, g__post1_self__tlb_mapping_4k___2__dom___leneq: bool, k__post1_self__tlb_mapping_4k___2__dom___leneq: nat, g__post1_self__tlb_mapping_4k___2__dom___lenrng: bool, k__post1_self__tlb_mapping_4k___2__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_4k___2__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_4k___2__dom___contains: bool, k__post1_self__tlb_mapping_4k___2__dom___contains: VAddr, g__post1_self__tlb_mapping_4k___3__dom___empty: bool, g__post1_self__tlb_mapping_4k___3__dom___lengt: bool, g__post1_self__tlb_mapping_4k___3__dom___leneq: bool, k__post1_self__tlb_mapping_4k___3__dom___leneq: nat, g__post1_self__tlb_mapping_4k___3__dom___lenrng: bool, k__post1_self__tlb_mapping_4k___3__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_4k___3__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_4k___3__dom___contains: bool, k__post1_self__tlb_mapping_4k___3__dom___contains: VAddr, g__post1_self__tlb_mapping_4k___4__dom___empty: bool, g__post1_self__tlb_mapping_4k___4__dom___lengt: bool, g__post1_self__tlb_mapping_4k___4__dom___leneq: bool, k__post1_self__tlb_mapping_4k___4__dom___leneq: nat, g__post1_self__tlb_mapping_4k___4__dom___lenrng: bool, k__post1_self__tlb_mapping_4k___4__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_4k___4__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_4k___4__dom___contains: bool, k__post1_self__tlb_mapping_4k___4__dom___contains: VAddr, g__post1_self__tlb_mapping_4k___5__dom___empty: bool, g__post1_self__tlb_mapping_4k___5__dom___lengt: bool, g__post1_self__tlb_mapping_4k___5__dom___leneq: bool, k__post1_self__tlb_mapping_4k___5__dom___leneq: nat, g__post1_self__tlb_mapping_4k___5__dom___lenrng: bool, k__post1_self__tlb_mapping_4k___5__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_4k___5__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_4k___5__dom___contains: bool, k__post1_self__tlb_mapping_4k___5__dom___contains: VAddr, g__post1_self__tlb_mapping_4k___6__dom___empty: bool, g__post1_self__tlb_mapping_4k___6__dom___lengt: bool, g__post1_self__tlb_mapping_4k___6__dom___leneq: bool, k__post1_self__tlb_mapping_4k___6__dom___leneq: nat, g__post1_self__tlb_mapping_4k___6__dom___lenrng: bool, k__post1_self__tlb_mapping_4k___6__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_4k___6__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_4k___6__dom___contains: bool, k__post1_self__tlb_mapping_4k___6__dom___contains: VAddr, g__post1_self__tlb_mapping_4k___7__dom___empty: bool, g__post1_self__tlb_mapping_4k___7__dom___lengt: bool, g__post1_self__tlb_mapping_4k___7__dom___leneq: bool, k__post1_self__tlb_mapping_4k___7__dom___leneq: nat, g__post1_self__tlb_mapping_4k___7__dom___lenrng: bool, k__post1_self__tlb_mapping_4k___7__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_4k___7__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_4k___7__dom___contains: bool, k__post1_self__tlb_mapping_4k___7__dom___contains: VAddr, g__post1_self__tlb_mapping_2m___leneq: bool, k__post1_self__tlb_mapping_2m___leneq: nat, g__post1_self__tlb_mapping_2m___lenrng: bool, k__post1_self__tlb_mapping_2m___lenrng_lo: nat, k__post1_self__tlb_mapping_2m___lenrng_hi: nat, g__post1_self__tlb_mapping_2m___0__dom___empty: bool, g__post1_self__tlb_mapping_2m___0__dom___lengt: bool, g__post1_self__tlb_mapping_2m___0__dom___leneq: bool, k__post1_self__tlb_mapping_2m___0__dom___leneq: nat, g__post1_self__tlb_mapping_2m___0__dom___lenrng: bool, k__post1_self__tlb_mapping_2m___0__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_2m___0__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_2m___0__dom___contains: bool, k__post1_self__tlb_mapping_2m___0__dom___contains: VAddr, g__post1_self__tlb_mapping_2m___1__dom___empty: bool, g__post1_self__tlb_mapping_2m___1__dom___lengt: bool, g__post1_self__tlb_mapping_2m___1__dom___leneq: bool, k__post1_self__tlb_mapping_2m___1__dom___leneq: nat, g__post1_self__tlb_mapping_2m___1__dom___lenrng: bool, k__post1_self__tlb_mapping_2m___1__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_2m___1__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_2m___1__dom___contains: bool, k__post1_self__tlb_mapping_2m___1__dom___contains: VAddr, g__post1_self__tlb_mapping_2m___2__dom___empty: bool, g__post1_self__tlb_mapping_2m___2__dom___lengt: bool, g__post1_self__tlb_mapping_2m___2__dom___leneq: bool, k__post1_self__tlb_mapping_2m___2__dom___leneq: nat, g__post1_self__tlb_mapping_2m___2__dom___lenrng: bool, k__post1_self__tlb_mapping_2m___2__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_2m___2__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_2m___2__dom___contains: bool, k__post1_self__tlb_mapping_2m___2__dom___contains: VAddr, g__post1_self__tlb_mapping_2m___3__dom___empty: bool, g__post1_self__tlb_mapping_2m___3__dom___lengt: bool, g__post1_self__tlb_mapping_2m___3__dom___leneq: bool, k__post1_self__tlb_mapping_2m___3__dom___leneq: nat, g__post1_self__tlb_mapping_2m___3__dom___lenrng: bool, k__post1_self__tlb_mapping_2m___3__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_2m___3__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_2m___3__dom___contains: bool, k__post1_self__tlb_mapping_2m___3__dom___contains: VAddr, g__post1_self__tlb_mapping_2m___4__dom___empty: bool, g__post1_self__tlb_mapping_2m___4__dom___lengt: bool, g__post1_self__tlb_mapping_2m___4__dom___leneq: bool, k__post1_self__tlb_mapping_2m___4__dom___leneq: nat, g__post1_self__tlb_mapping_2m___4__dom___lenrng: bool, k__post1_self__tlb_mapping_2m___4__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_2m___4__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_2m___4__dom___contains: bool, k__post1_self__tlb_mapping_2m___4__dom___contains: VAddr, g__post1_self__tlb_mapping_2m___5__dom___empty: bool, g__post1_self__tlb_mapping_2m___5__dom___lengt: bool, g__post1_self__tlb_mapping_2m___5__dom___leneq: bool, k__post1_self__tlb_mapping_2m___5__dom___leneq: nat, g__post1_self__tlb_mapping_2m___5__dom___lenrng: bool, k__post1_self__tlb_mapping_2m___5__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_2m___5__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_2m___5__dom___contains: bool, k__post1_self__tlb_mapping_2m___5__dom___contains: VAddr, g__post1_self__tlb_mapping_2m___6__dom___empty: bool, g__post1_self__tlb_mapping_2m___6__dom___lengt: bool, g__post1_self__tlb_mapping_2m___6__dom___leneq: bool, k__post1_self__tlb_mapping_2m___6__dom___leneq: nat, g__post1_self__tlb_mapping_2m___6__dom___lenrng: bool, k__post1_self__tlb_mapping_2m___6__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_2m___6__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_2m___6__dom___contains: bool, k__post1_self__tlb_mapping_2m___6__dom___contains: VAddr, g__post1_self__tlb_mapping_2m___7__dom___empty: bool, g__post1_self__tlb_mapping_2m___7__dom___lengt: bool, g__post1_self__tlb_mapping_2m___7__dom___leneq: bool, k__post1_self__tlb_mapping_2m___7__dom___leneq: nat, g__post1_self__tlb_mapping_2m___7__dom___lenrng: bool, k__post1_self__tlb_mapping_2m___7__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_2m___7__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_2m___7__dom___contains: bool, k__post1_self__tlb_mapping_2m___7__dom___contains: VAddr, g__post1_self__tlb_mapping_1g___leneq: bool, k__post1_self__tlb_mapping_1g___leneq: nat, g__post1_self__tlb_mapping_1g___lenrng: bool, k__post1_self__tlb_mapping_1g___lenrng_lo: nat, k__post1_self__tlb_mapping_1g___lenrng_hi: nat, g__post1_self__tlb_mapping_1g___0__dom___empty: bool, g__post1_self__tlb_mapping_1g___0__dom___lengt: bool, g__post1_self__tlb_mapping_1g___0__dom___leneq: bool, k__post1_self__tlb_mapping_1g___0__dom___leneq: nat, g__post1_self__tlb_mapping_1g___0__dom___lenrng: bool, k__post1_self__tlb_mapping_1g___0__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_1g___0__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_1g___0__dom___contains: bool, k__post1_self__tlb_mapping_1g___0__dom___contains: VAddr, g__post1_self__tlb_mapping_1g___1__dom___empty: bool, g__post1_self__tlb_mapping_1g___1__dom___lengt: bool, g__post1_self__tlb_mapping_1g___1__dom___leneq: bool, k__post1_self__tlb_mapping_1g___1__dom___leneq: nat, g__post1_self__tlb_mapping_1g___1__dom___lenrng: bool, k__post1_self__tlb_mapping_1g___1__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_1g___1__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_1g___1__dom___contains: bool, k__post1_self__tlb_mapping_1g___1__dom___contains: VAddr, g__post1_self__tlb_mapping_1g___2__dom___empty: bool, g__post1_self__tlb_mapping_1g___2__dom___lengt: bool, g__post1_self__tlb_mapping_1g___2__dom___leneq: bool, k__post1_self__tlb_mapping_1g___2__dom___leneq: nat, g__post1_self__tlb_mapping_1g___2__dom___lenrng: bool, k__post1_self__tlb_mapping_1g___2__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_1g___2__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_1g___2__dom___contains: bool, k__post1_self__tlb_mapping_1g___2__dom___contains: VAddr, g__post1_self__tlb_mapping_1g___3__dom___empty: bool, g__post1_self__tlb_mapping_1g___3__dom___lengt: bool, g__post1_self__tlb_mapping_1g___3__dom___leneq: bool, k__post1_self__tlb_mapping_1g___3__dom___leneq: nat, g__post1_self__tlb_mapping_1g___3__dom___lenrng: bool, k__post1_self__tlb_mapping_1g___3__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_1g___3__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_1g___3__dom___contains: bool, k__post1_self__tlb_mapping_1g___3__dom___contains: VAddr, g__post1_self__tlb_mapping_1g___4__dom___empty: bool, g__post1_self__tlb_mapping_1g___4__dom___lengt: bool, g__post1_self__tlb_mapping_1g___4__dom___leneq: bool, k__post1_self__tlb_mapping_1g___4__dom___leneq: nat, g__post1_self__tlb_mapping_1g___4__dom___lenrng: bool, k__post1_self__tlb_mapping_1g___4__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_1g___4__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_1g___4__dom___contains: bool, k__post1_self__tlb_mapping_1g___4__dom___contains: VAddr, g__post1_self__tlb_mapping_1g___5__dom___empty: bool, g__post1_self__tlb_mapping_1g___5__dom___lengt: bool, g__post1_self__tlb_mapping_1g___5__dom___leneq: bool, k__post1_self__tlb_mapping_1g___5__dom___leneq: nat, g__post1_self__tlb_mapping_1g___5__dom___lenrng: bool, k__post1_self__tlb_mapping_1g___5__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_1g___5__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_1g___5__dom___contains: bool, k__post1_self__tlb_mapping_1g___5__dom___contains: VAddr, g__post1_self__tlb_mapping_1g___6__dom___empty: bool, g__post1_self__tlb_mapping_1g___6__dom___lengt: bool, g__post1_self__tlb_mapping_1g___6__dom___leneq: bool, k__post1_self__tlb_mapping_1g___6__dom___leneq: nat, g__post1_self__tlb_mapping_1g___6__dom___lenrng: bool, k__post1_self__tlb_mapping_1g___6__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_1g___6__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_1g___6__dom___contains: bool, k__post1_self__tlb_mapping_1g___6__dom___contains: VAddr, g__post1_self__tlb_mapping_1g___7__dom___empty: bool, g__post1_self__tlb_mapping_1g___7__dom___lengt: bool, g__post1_self__tlb_mapping_1g___7__dom___leneq: bool, k__post1_self__tlb_mapping_1g___7__dom___leneq: nat, g__post1_self__tlb_mapping_1g___7__dom___lenrng: bool, k__post1_self__tlb_mapping_1g___7__dom___lenrng_lo: nat, k__post1_self__tlb_mapping_1g___7__dom___lenrng_hi: nat, g__post1_self__tlb_mapping_1g___7__dom___contains: bool, k__post1_self__tlb_mapping_1g___7__dom___contains: VAddr, g_post2_self__pcid_is_Some: bool, g_post2_self__pcid_is_None: bool, g_post2_self__ioid_is_Some: bool, g_post2_self__ioid_is_None: bool, g_post2_self__kernel_l4_end_eq: bool, k_post2_self__kernel_l4_end_eq: int, g_post2_self__kernel_l4_end_rng: bool, k_post2_self__kernel_l4_end_rng_lo: int, k_post2_self__kernel_l4_end_rng_hi: int, g__post2_self__l4_table___dom___empty: bool, g__post2_self__l4_table___dom___lengt: bool, g__post2_self__l4_table___dom___leneq: bool, k__post2_self__l4_table___dom___leneq: nat, g__post2_self__l4_table___dom___lenrng: bool, k__post2_self__l4_table___dom___lenrng_lo: nat, k__post2_self__l4_table___dom___lenrng_hi: nat, g__post2_self__l4_table___dom___contains: bool, k__post2_self__l4_table___dom___contains: PageMapPtr, g__post2_self__l3_rev_map___dom___empty: bool, g__post2_self__l3_rev_map___dom___lengt: bool, g__post2_self__l3_rev_map___dom___leneq: bool, k__post2_self__l3_rev_map___dom___leneq: nat, g__post2_self__l3_rev_map___dom___lenrng: bool, k__post2_self__l3_rev_map___dom___lenrng_lo: nat, k__post2_self__l3_rev_map___dom___lenrng_hi: nat, g__post2_self__l3_rev_map___dom___contains: bool, k__post2_self__l3_rev_map___dom___contains: PageMapPtr, g__post2_self__l3_tables___dom___empty: bool, g__post2_self__l3_tables___dom___lengt: bool, g__post2_self__l3_tables___dom___leneq: bool, k__post2_self__l3_tables___dom___leneq: nat, g__post2_self__l3_tables___dom___lenrng: bool, k__post2_self__l3_tables___dom___lenrng_lo: nat, k__post2_self__l3_tables___dom___lenrng_hi: nat, g__post2_self__l3_tables___dom___contains: bool, k__post2_self__l3_tables___dom___contains: PageMapPtr, g__post2_self__l2_rev_map___dom___empty: bool, g__post2_self__l2_rev_map___dom___lengt: bool, g__post2_self__l2_rev_map___dom___leneq: bool, k__post2_self__l2_rev_map___dom___leneq: nat, g__post2_self__l2_rev_map___dom___lenrng: bool, k__post2_self__l2_rev_map___dom___lenrng_lo: nat, k__post2_self__l2_rev_map___dom___lenrng_hi: nat, g__post2_self__l2_rev_map___dom___contains: bool, k__post2_self__l2_rev_map___dom___contains: PageMapPtr, g__post2_self__l2_tables___dom___empty: bool, g__post2_self__l2_tables___dom___lengt: bool, g__post2_self__l2_tables___dom___leneq: bool, k__post2_self__l2_tables___dom___leneq: nat, g__post2_self__l2_tables___dom___lenrng: bool, k__post2_self__l2_tables___dom___lenrng_lo: nat, k__post2_self__l2_tables___dom___lenrng_hi: nat, g__post2_self__l2_tables___dom___contains: bool, k__post2_self__l2_tables___dom___contains: PageMapPtr, g__post2_self__l1_rev_map___dom___empty: bool, g__post2_self__l1_rev_map___dom___lengt: bool, g__post2_self__l1_rev_map___dom___leneq: bool, k__post2_self__l1_rev_map___dom___leneq: nat, g__post2_self__l1_rev_map___dom___lenrng: bool, k__post2_self__l1_rev_map___dom___lenrng_lo: nat, k__post2_self__l1_rev_map___dom___lenrng_hi: nat, g__post2_self__l1_rev_map___dom___contains: bool, k__post2_self__l1_rev_map___dom___contains: PageMapPtr, g__post2_self__l1_tables___dom___empty: bool, g__post2_self__l1_tables___dom___lengt: bool, g__post2_self__l1_tables___dom___leneq: bool, k__post2_self__l1_tables___dom___leneq: nat, g__post2_self__l1_tables___dom___lenrng: bool, k__post2_self__l1_tables___dom___lenrng_lo: nat, k__post2_self__l1_tables___dom___lenrng_hi: nat, g__post2_self__l1_tables___dom___contains: bool, k__post2_self__l1_tables___dom___contains: PageMapPtr, g__post2_self__mapping_4k___dom___empty: bool, g__post2_self__mapping_4k___dom___lengt: bool, g__post2_self__mapping_4k___dom___leneq: bool, k__post2_self__mapping_4k___dom___leneq: nat, g__post2_self__mapping_4k___dom___lenrng: bool, k__post2_self__mapping_4k___dom___lenrng_lo: nat, k__post2_self__mapping_4k___dom___lenrng_hi: nat, g__post2_self__mapping_4k___dom___contains: bool, k__post2_self__mapping_4k___dom___contains: VAddr, g__post2_self__mapping_2m___dom___empty: bool, g__post2_self__mapping_2m___dom___lengt: bool, g__post2_self__mapping_2m___dom___leneq: bool, k__post2_self__mapping_2m___dom___leneq: nat, g__post2_self__mapping_2m___dom___lenrng: bool, k__post2_self__mapping_2m___dom___lenrng_lo: nat, k__post2_self__mapping_2m___dom___lenrng_hi: nat, g__post2_self__mapping_2m___dom___contains: bool, k__post2_self__mapping_2m___dom___contains: VAddr, g__post2_self__mapping_1g___dom___empty: bool, g__post2_self__mapping_1g___dom___lengt: bool, g__post2_self__mapping_1g___dom___leneq: bool, k__post2_self__mapping_1g___dom___leneq: nat, g__post2_self__mapping_1g___dom___lenrng: bool, k__post2_self__mapping_1g___dom___lenrng_lo: nat, k__post2_self__mapping_1g___dom___lenrng_hi: nat, g__post2_self__mapping_1g___dom___contains: bool, k__post2_self__mapping_1g___dom___contains: VAddr, g__post2_self__kernel_entries___leneq: bool, k__post2_self__kernel_entries___leneq: nat, g__post2_self__kernel_entries___lenrng: bool, k__post2_self__kernel_entries___lenrng_lo: nat, k__post2_self__kernel_entries___lenrng_hi: nat, g__post2_self__kernel_entries___0__perm_present_is_true: bool, g__post2_self__kernel_entries___0__perm_present_is_false: bool, g__post2_self__kernel_entries___0__perm_ps_is_true: bool, g__post2_self__kernel_entries___0__perm_ps_is_false: bool, g__post2_self__kernel_entries___0__perm_write_is_true: bool, g__post2_self__kernel_entries___0__perm_write_is_false: bool, g__post2_self__kernel_entries___0__perm_execute_disable_is_true: bool, g__post2_self__kernel_entries___0__perm_execute_disable_is_false: bool, g__post2_self__kernel_entries___0__perm_user_is_true: bool, g__post2_self__kernel_entries___0__perm_user_is_false: bool, g__post2_self__kernel_entries___1__perm_present_is_true: bool, g__post2_self__kernel_entries___1__perm_present_is_false: bool, g__post2_self__kernel_entries___1__perm_ps_is_true: bool, g__post2_self__kernel_entries___1__perm_ps_is_false: bool, g__post2_self__kernel_entries___1__perm_write_is_true: bool, g__post2_self__kernel_entries___1__perm_write_is_false: bool, g__post2_self__kernel_entries___1__perm_execute_disable_is_true: bool, g__post2_self__kernel_entries___1__perm_execute_disable_is_false: bool, g__post2_self__kernel_entries___1__perm_user_is_true: bool, g__post2_self__kernel_entries___1__perm_user_is_false: bool, g__post2_self__kernel_entries___2__perm_present_is_true: bool, g__post2_self__kernel_entries___2__perm_present_is_false: bool, g__post2_self__kernel_entries___2__perm_ps_is_true: bool, g__post2_self__kernel_entries___2__perm_ps_is_false: bool, g__post2_self__kernel_entries___2__perm_write_is_true: bool, g__post2_self__kernel_entries___2__perm_write_is_false: bool, g__post2_self__kernel_entries___2__perm_execute_disable_is_true: bool, g__post2_self__kernel_entries___2__perm_execute_disable_is_false: bool, g__post2_self__kernel_entries___2__perm_user_is_true: bool, g__post2_self__kernel_entries___2__perm_user_is_false: bool, g__post2_self__kernel_entries___3__perm_present_is_true: bool, g__post2_self__kernel_entries___3__perm_present_is_false: bool, g__post2_self__kernel_entries___3__perm_ps_is_true: bool, g__post2_self__kernel_entries___3__perm_ps_is_false: bool, g__post2_self__kernel_entries___3__perm_write_is_true: bool, g__post2_self__kernel_entries___3__perm_write_is_false: bool, g__post2_self__kernel_entries___3__perm_execute_disable_is_true: bool, g__post2_self__kernel_entries___3__perm_execute_disable_is_false: bool, g__post2_self__kernel_entries___3__perm_user_is_true: bool, g__post2_self__kernel_entries___3__perm_user_is_false: bool, g__post2_self__kernel_entries___4__perm_present_is_true: bool, g__post2_self__kernel_entries___4__perm_present_is_false: bool, g__post2_self__kernel_entries___4__perm_ps_is_true: bool, g__post2_self__kernel_entries___4__perm_ps_is_false: bool, g__post2_self__kernel_entries___4__perm_write_is_true: bool, g__post2_self__kernel_entries___4__perm_write_is_false: bool, g__post2_self__kernel_entries___4__perm_execute_disable_is_true: bool, g__post2_self__kernel_entries___4__perm_execute_disable_is_false: bool, g__post2_self__kernel_entries___4__perm_user_is_true: bool, g__post2_self__kernel_entries___4__perm_user_is_false: bool, g__post2_self__kernel_entries___5__perm_present_is_true: bool, g__post2_self__kernel_entries___5__perm_present_is_false: bool, g__post2_self__kernel_entries___5__perm_ps_is_true: bool, g__post2_self__kernel_entries___5__perm_ps_is_false: bool, g__post2_self__kernel_entries___5__perm_write_is_true: bool, g__post2_self__kernel_entries___5__perm_write_is_false: bool, g__post2_self__kernel_entries___5__perm_execute_disable_is_true: bool, g__post2_self__kernel_entries___5__perm_execute_disable_is_false: bool, g__post2_self__kernel_entries___5__perm_user_is_true: bool, g__post2_self__kernel_entries___5__perm_user_is_false: bool, g__post2_self__kernel_entries___6__perm_present_is_true: bool, g__post2_self__kernel_entries___6__perm_present_is_false: bool, g__post2_self__kernel_entries___6__perm_ps_is_true: bool, g__post2_self__kernel_entries___6__perm_ps_is_false: bool, g__post2_self__kernel_entries___6__perm_write_is_true: bool, g__post2_self__kernel_entries___6__perm_write_is_false: bool, g__post2_self__kernel_entries___6__perm_execute_disable_is_true: bool, g__post2_self__kernel_entries___6__perm_execute_disable_is_false: bool, g__post2_self__kernel_entries___6__perm_user_is_true: bool, g__post2_self__kernel_entries___6__perm_user_is_false: bool, g__post2_self__kernel_entries___7__perm_present_is_true: bool, g__post2_self__kernel_entries___7__perm_present_is_false: bool, g__post2_self__kernel_entries___7__perm_ps_is_true: bool, g__post2_self__kernel_entries___7__perm_ps_is_false: bool, g__post2_self__kernel_entries___7__perm_write_is_true: bool, g__post2_self__kernel_entries___7__perm_write_is_false: bool, g__post2_self__kernel_entries___7__perm_execute_disable_is_true: bool, g__post2_self__kernel_entries___7__perm_execute_disable_is_false: bool, g__post2_self__kernel_entries___7__perm_user_is_true: bool, g__post2_self__kernel_entries___7__perm_user_is_false: bool, g__post2_self__tlb_mapping_4k___leneq: bool, k__post2_self__tlb_mapping_4k___leneq: nat, g__post2_self__tlb_mapping_4k___lenrng: bool, k__post2_self__tlb_mapping_4k___lenrng_lo: nat, k__post2_self__tlb_mapping_4k___lenrng_hi: nat, g__post2_self__tlb_mapping_4k___0__dom___empty: bool, g__post2_self__tlb_mapping_4k___0__dom___lengt: bool, g__post2_self__tlb_mapping_4k___0__dom___leneq: bool, k__post2_self__tlb_mapping_4k___0__dom___leneq: nat, g__post2_self__tlb_mapping_4k___0__dom___lenrng: bool, k__post2_self__tlb_mapping_4k___0__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_4k___0__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_4k___0__dom___contains: bool, k__post2_self__tlb_mapping_4k___0__dom___contains: VAddr, g__post2_self__tlb_mapping_4k___1__dom___empty: bool, g__post2_self__tlb_mapping_4k___1__dom___lengt: bool, g__post2_self__tlb_mapping_4k___1__dom___leneq: bool, k__post2_self__tlb_mapping_4k___1__dom___leneq: nat, g__post2_self__tlb_mapping_4k___1__dom___lenrng: bool, k__post2_self__tlb_mapping_4k___1__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_4k___1__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_4k___1__dom___contains: bool, k__post2_self__tlb_mapping_4k___1__dom___contains: VAddr, g__post2_self__tlb_mapping_4k___2__dom___empty: bool, g__post2_self__tlb_mapping_4k___2__dom___lengt: bool, g__post2_self__tlb_mapping_4k___2__dom___leneq: bool, k__post2_self__tlb_mapping_4k___2__dom___leneq: nat, g__post2_self__tlb_mapping_4k___2__dom___lenrng: bool, k__post2_self__tlb_mapping_4k___2__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_4k___2__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_4k___2__dom___contains: bool, k__post2_self__tlb_mapping_4k___2__dom___contains: VAddr, g__post2_self__tlb_mapping_4k___3__dom___empty: bool, g__post2_self__tlb_mapping_4k___3__dom___lengt: bool, g__post2_self__tlb_mapping_4k___3__dom___leneq: bool, k__post2_self__tlb_mapping_4k___3__dom___leneq: nat, g__post2_self__tlb_mapping_4k___3__dom___lenrng: bool, k__post2_self__tlb_mapping_4k___3__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_4k___3__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_4k___3__dom___contains: bool, k__post2_self__tlb_mapping_4k___3__dom___contains: VAddr, g__post2_self__tlb_mapping_4k___4__dom___empty: bool, g__post2_self__tlb_mapping_4k___4__dom___lengt: bool, g__post2_self__tlb_mapping_4k___4__dom___leneq: bool, k__post2_self__tlb_mapping_4k___4__dom___leneq: nat, g__post2_self__tlb_mapping_4k___4__dom___lenrng: bool, k__post2_self__tlb_mapping_4k___4__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_4k___4__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_4k___4__dom___contains: bool, k__post2_self__tlb_mapping_4k___4__dom___contains: VAddr, g__post2_self__tlb_mapping_4k___5__dom___empty: bool, g__post2_self__tlb_mapping_4k___5__dom___lengt: bool, g__post2_self__tlb_mapping_4k___5__dom___leneq: bool, k__post2_self__tlb_mapping_4k___5__dom___leneq: nat, g__post2_self__tlb_mapping_4k___5__dom___lenrng: bool, k__post2_self__tlb_mapping_4k___5__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_4k___5__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_4k___5__dom___contains: bool, k__post2_self__tlb_mapping_4k___5__dom___contains: VAddr, g__post2_self__tlb_mapping_4k___6__dom___empty: bool, g__post2_self__tlb_mapping_4k___6__dom___lengt: bool, g__post2_self__tlb_mapping_4k___6__dom___leneq: bool, k__post2_self__tlb_mapping_4k___6__dom___leneq: nat, g__post2_self__tlb_mapping_4k___6__dom___lenrng: bool, k__post2_self__tlb_mapping_4k___6__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_4k___6__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_4k___6__dom___contains: bool, k__post2_self__tlb_mapping_4k___6__dom___contains: VAddr, g__post2_self__tlb_mapping_4k___7__dom___empty: bool, g__post2_self__tlb_mapping_4k___7__dom___lengt: bool, g__post2_self__tlb_mapping_4k___7__dom___leneq: bool, k__post2_self__tlb_mapping_4k___7__dom___leneq: nat, g__post2_self__tlb_mapping_4k___7__dom___lenrng: bool, k__post2_self__tlb_mapping_4k___7__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_4k___7__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_4k___7__dom___contains: bool, k__post2_self__tlb_mapping_4k___7__dom___contains: VAddr, g__post2_self__tlb_mapping_2m___leneq: bool, k__post2_self__tlb_mapping_2m___leneq: nat, g__post2_self__tlb_mapping_2m___lenrng: bool, k__post2_self__tlb_mapping_2m___lenrng_lo: nat, k__post2_self__tlb_mapping_2m___lenrng_hi: nat, g__post2_self__tlb_mapping_2m___0__dom___empty: bool, g__post2_self__tlb_mapping_2m___0__dom___lengt: bool, g__post2_self__tlb_mapping_2m___0__dom___leneq: bool, k__post2_self__tlb_mapping_2m___0__dom___leneq: nat, g__post2_self__tlb_mapping_2m___0__dom___lenrng: bool, k__post2_self__tlb_mapping_2m___0__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_2m___0__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_2m___0__dom___contains: bool, k__post2_self__tlb_mapping_2m___0__dom___contains: VAddr, g__post2_self__tlb_mapping_2m___1__dom___empty: bool, g__post2_self__tlb_mapping_2m___1__dom___lengt: bool, g__post2_self__tlb_mapping_2m___1__dom___leneq: bool, k__post2_self__tlb_mapping_2m___1__dom___leneq: nat, g__post2_self__tlb_mapping_2m___1__dom___lenrng: bool, k__post2_self__tlb_mapping_2m___1__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_2m___1__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_2m___1__dom___contains: bool, k__post2_self__tlb_mapping_2m___1__dom___contains: VAddr, g__post2_self__tlb_mapping_2m___2__dom___empty: bool, g__post2_self__tlb_mapping_2m___2__dom___lengt: bool, g__post2_self__tlb_mapping_2m___2__dom___leneq: bool, k__post2_self__tlb_mapping_2m___2__dom___leneq: nat, g__post2_self__tlb_mapping_2m___2__dom___lenrng: bool, k__post2_self__tlb_mapping_2m___2__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_2m___2__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_2m___2__dom___contains: bool, k__post2_self__tlb_mapping_2m___2__dom___contains: VAddr, g__post2_self__tlb_mapping_2m___3__dom___empty: bool, g__post2_self__tlb_mapping_2m___3__dom___lengt: bool, g__post2_self__tlb_mapping_2m___3__dom___leneq: bool, k__post2_self__tlb_mapping_2m___3__dom___leneq: nat, g__post2_self__tlb_mapping_2m___3__dom___lenrng: bool, k__post2_self__tlb_mapping_2m___3__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_2m___3__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_2m___3__dom___contains: bool, k__post2_self__tlb_mapping_2m___3__dom___contains: VAddr, g__post2_self__tlb_mapping_2m___4__dom___empty: bool, g__post2_self__tlb_mapping_2m___4__dom___lengt: bool, g__post2_self__tlb_mapping_2m___4__dom___leneq: bool, k__post2_self__tlb_mapping_2m___4__dom___leneq: nat, g__post2_self__tlb_mapping_2m___4__dom___lenrng: bool, k__post2_self__tlb_mapping_2m___4__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_2m___4__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_2m___4__dom___contains: bool, k__post2_self__tlb_mapping_2m___4__dom___contains: VAddr, g__post2_self__tlb_mapping_2m___5__dom___empty: bool, g__post2_self__tlb_mapping_2m___5__dom___lengt: bool, g__post2_self__tlb_mapping_2m___5__dom___leneq: bool, k__post2_self__tlb_mapping_2m___5__dom___leneq: nat, g__post2_self__tlb_mapping_2m___5__dom___lenrng: bool, k__post2_self__tlb_mapping_2m___5__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_2m___5__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_2m___5__dom___contains: bool, k__post2_self__tlb_mapping_2m___5__dom___contains: VAddr, g__post2_self__tlb_mapping_2m___6__dom___empty: bool, g__post2_self__tlb_mapping_2m___6__dom___lengt: bool, g__post2_self__tlb_mapping_2m___6__dom___leneq: bool, k__post2_self__tlb_mapping_2m___6__dom___leneq: nat, g__post2_self__tlb_mapping_2m___6__dom___lenrng: bool, k__post2_self__tlb_mapping_2m___6__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_2m___6__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_2m___6__dom___contains: bool, k__post2_self__tlb_mapping_2m___6__dom___contains: VAddr, g__post2_self__tlb_mapping_2m___7__dom___empty: bool, g__post2_self__tlb_mapping_2m___7__dom___lengt: bool, g__post2_self__tlb_mapping_2m___7__dom___leneq: bool, k__post2_self__tlb_mapping_2m___7__dom___leneq: nat, g__post2_self__tlb_mapping_2m___7__dom___lenrng: bool, k__post2_self__tlb_mapping_2m___7__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_2m___7__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_2m___7__dom___contains: bool, k__post2_self__tlb_mapping_2m___7__dom___contains: VAddr, g__post2_self__tlb_mapping_1g___leneq: bool, k__post2_self__tlb_mapping_1g___leneq: nat, g__post2_self__tlb_mapping_1g___lenrng: bool, k__post2_self__tlb_mapping_1g___lenrng_lo: nat, k__post2_self__tlb_mapping_1g___lenrng_hi: nat, g__post2_self__tlb_mapping_1g___0__dom___empty: bool, g__post2_self__tlb_mapping_1g___0__dom___lengt: bool, g__post2_self__tlb_mapping_1g___0__dom___leneq: bool, k__post2_self__tlb_mapping_1g___0__dom___leneq: nat, g__post2_self__tlb_mapping_1g___0__dom___lenrng: bool, k__post2_self__tlb_mapping_1g___0__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_1g___0__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_1g___0__dom___contains: bool, k__post2_self__tlb_mapping_1g___0__dom___contains: VAddr, g__post2_self__tlb_mapping_1g___1__dom___empty: bool, g__post2_self__tlb_mapping_1g___1__dom___lengt: bool, g__post2_self__tlb_mapping_1g___1__dom___leneq: bool, k__post2_self__tlb_mapping_1g___1__dom___leneq: nat, g__post2_self__tlb_mapping_1g___1__dom___lenrng: bool, k__post2_self__tlb_mapping_1g___1__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_1g___1__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_1g___1__dom___contains: bool, k__post2_self__tlb_mapping_1g___1__dom___contains: VAddr, g__post2_self__tlb_mapping_1g___2__dom___empty: bool, g__post2_self__tlb_mapping_1g___2__dom___lengt: bool, g__post2_self__tlb_mapping_1g___2__dom___leneq: bool, k__post2_self__tlb_mapping_1g___2__dom___leneq: nat, g__post2_self__tlb_mapping_1g___2__dom___lenrng: bool, k__post2_self__tlb_mapping_1g___2__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_1g___2__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_1g___2__dom___contains: bool, k__post2_self__tlb_mapping_1g___2__dom___contains: VAddr, g__post2_self__tlb_mapping_1g___3__dom___empty: bool, g__post2_self__tlb_mapping_1g___3__dom___lengt: bool, g__post2_self__tlb_mapping_1g___3__dom___leneq: bool, k__post2_self__tlb_mapping_1g___3__dom___leneq: nat, g__post2_self__tlb_mapping_1g___3__dom___lenrng: bool, k__post2_self__tlb_mapping_1g___3__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_1g___3__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_1g___3__dom___contains: bool, k__post2_self__tlb_mapping_1g___3__dom___contains: VAddr, g__post2_self__tlb_mapping_1g___4__dom___empty: bool, g__post2_self__tlb_mapping_1g___4__dom___lengt: bool, g__post2_self__tlb_mapping_1g___4__dom___leneq: bool, k__post2_self__tlb_mapping_1g___4__dom___leneq: nat, g__post2_self__tlb_mapping_1g___4__dom___lenrng: bool, k__post2_self__tlb_mapping_1g___4__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_1g___4__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_1g___4__dom___contains: bool, k__post2_self__tlb_mapping_1g___4__dom___contains: VAddr, g__post2_self__tlb_mapping_1g___5__dom___empty: bool, g__post2_self__tlb_mapping_1g___5__dom___lengt: bool, g__post2_self__tlb_mapping_1g___5__dom___leneq: bool, k__post2_self__tlb_mapping_1g___5__dom___leneq: nat, g__post2_self__tlb_mapping_1g___5__dom___lenrng: bool, k__post2_self__tlb_mapping_1g___5__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_1g___5__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_1g___5__dom___contains: bool, k__post2_self__tlb_mapping_1g___5__dom___contains: VAddr, g__post2_self__tlb_mapping_1g___6__dom___empty: bool, g__post2_self__tlb_mapping_1g___6__dom___lengt: bool, g__post2_self__tlb_mapping_1g___6__dom___leneq: bool, k__post2_self__tlb_mapping_1g___6__dom___leneq: nat, g__post2_self__tlb_mapping_1g___6__dom___lenrng: bool, k__post2_self__tlb_mapping_1g___6__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_1g___6__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_1g___6__dom___contains: bool, k__post2_self__tlb_mapping_1g___6__dom___contains: VAddr, g__post2_self__tlb_mapping_1g___7__dom___empty: bool, g__post2_self__tlb_mapping_1g___7__dom___lengt: bool, g__post2_self__tlb_mapping_1g___7__dom___leneq: bool, k__post2_self__tlb_mapping_1g___7__dom___leneq: nat, g__post2_self__tlb_mapping_1g___7__dom___lenrng: bool, k__post2_self__tlb_mapping_1g___7__dom___lenrng_lo: nat, k__post2_self__tlb_mapping_1g___7__dom___lenrng_hi: nat, g__post2_self__tlb_mapping_1g___7__dom___contains: bool, k__post2_self__tlb_mapping_1g___7__dom___contains: VAddr, g_neq_tuple: bool, pre_self_: PageTable, target_l4i: L4Index, target_l3i: L3Index, target_l2i: L2Index, target_l1i: L2Index, target_l1_p: PageMapPtr, target_entry: MapEntry, post1_self_: PageTable, r1: (), post2_self_: PageTable, r2: ())
    requires (pre_self_.wf()), (pre_self_.kernel_l4_end <= target_l4i < 512), (0 <= target_l3i < 512), (0 <= target_l2i < 512), (0 <= target_l1i < 512), (pre_self_.spec_resolve_mapping_l2(target_l4i, target_l3i, target_l2i).is_Some()), (pre_self_.spec_resolve_mapping_l2(target_l4i, target_l3i, target_l2i).get_Some_0().addr
                == target_l1_p), (pre_self_.spec_resolve_mapping_4k_l1(
                target_l4i,
                target_l3i,
                target_l2i,
                target_l1i,
            ).is_None() || pre_self_.mapping_4k().dom().contains(
                spec_index2va((target_l4i, target_l3i, target_l2i, target_l1i)),
            ) == false), (pre_self_.page_closure().contains(target_entry.addr) == false), (page_ptr_valid(target_entry.addr)),
    ensures
        ({
            &&& (post1_self_.wf())
            &&& (post1_self_.kernel_l4_end == pre_self_.kernel_l4_end)
            &&& (post1_self_.page_closure() =~= pre_self_.page_closure())
            &&& (post1_self_.mapping_4k@ == pre_self_.mapping_4k@.insert(
                spec_index2va((target_l4i, target_l3i, target_l2i, target_l1i)),
                target_entry,
            ))
            &&& (post1_self_.mapping_2m() =~= pre_self_.mapping_2m())
            &&& (post1_self_.mapping_1g() =~= pre_self_.mapping_1g())
            &&& (post1_self_.kernel_entries =~= pre_self_.kernel_entries)
            &&& (post2_self_.wf())
            &&& (post2_self_.kernel_l4_end == pre_self_.kernel_l4_end)
            &&& (post2_self_.page_closure() =~= pre_self_.page_closure())
            &&& (post2_self_.mapping_4k@ == pre_self_.mapping_4k@.insert(
                spec_index2va((target_l4i, target_l3i, target_l2i, target_l1i)),
                target_entry,
            ))
            &&& (post2_self_.mapping_2m() =~= pre_self_.mapping_2m())
            &&& (post2_self_.mapping_1g() =~= pre_self_.mapping_1g())
            &&& (post2_self_.kernel_entries =~= pre_self_.kernel_entries)
        }) ==> det_map_4k_page_equal(r1, r2, post1_self_, post2_self_),
{
    if g_pre_self__pcid_is_Some { assume(pre_self_.pcid is Some); }
    if g_pre_self__pcid_is_None { assume(pre_self_.pcid is None); }
    if g_pre_self__ioid_is_Some { assume(pre_self_.ioid is Some); }
    if g_pre_self__ioid_is_None { assume(pre_self_.ioid is None); }
    if g_pre_self__kernel_l4_end_eq { assume(pre_self_.kernel_l4_end as int == k_pre_self__kernel_l4_end_eq); }
    if g_pre_self__kernel_l4_end_rng { assume(pre_self_.kernel_l4_end as int >= k_pre_self__kernel_l4_end_rng_lo && pre_self_.kernel_l4_end as int <= k_pre_self__kernel_l4_end_rng_hi); }
    if g__pre_self__l4_table___dom___empty { assume((pre_self_.l4_table)@.dom() == Set::<PageMapPtr>::empty()); }
    if g__pre_self__l4_table___dom___lengt { assume((pre_self_.l4_table)@.dom().len() > 0); }
    if g__pre_self__l4_table___dom___leneq { assume((pre_self_.l4_table)@.dom().len() == k__pre_self__l4_table___dom___leneq); }
    if g__pre_self__l4_table___dom___lenrng { assume((pre_self_.l4_table)@.dom().len() >= k__pre_self__l4_table___dom___lenrng_lo && (pre_self_.l4_table)@.dom().len() <= k__pre_self__l4_table___dom___lenrng_hi); }
    if g__pre_self__l4_table___dom___contains { assume((pre_self_.l4_table)@.dom().contains(k__pre_self__l4_table___dom___contains)); }
    if g__pre_self__l3_rev_map___dom___empty { assume((pre_self_.l3_rev_map)@.dom() == Set::<PageMapPtr>::empty()); }
    if g__pre_self__l3_rev_map___dom___lengt { assume((pre_self_.l3_rev_map)@.dom().len() > 0); }
    if g__pre_self__l3_rev_map___dom___leneq { assume((pre_self_.l3_rev_map)@.dom().len() == k__pre_self__l3_rev_map___dom___leneq); }
    if g__pre_self__l3_rev_map___dom___lenrng { assume((pre_self_.l3_rev_map)@.dom().len() >= k__pre_self__l3_rev_map___dom___lenrng_lo && (pre_self_.l3_rev_map)@.dom().len() <= k__pre_self__l3_rev_map___dom___lenrng_hi); }
    if g__pre_self__l3_rev_map___dom___contains { assume((pre_self_.l3_rev_map)@.dom().contains(k__pre_self__l3_rev_map___dom___contains)); }
    if g__pre_self__l3_tables___dom___empty { assume((pre_self_.l3_tables)@.dom() == Set::<PageMapPtr>::empty()); }
    if g__pre_self__l3_tables___dom___lengt { assume((pre_self_.l3_tables)@.dom().len() > 0); }
    if g__pre_self__l3_tables___dom___leneq { assume((pre_self_.l3_tables)@.dom().len() == k__pre_self__l3_tables___dom___leneq); }
    if g__pre_self__l3_tables___dom___lenrng { assume((pre_self_.l3_tables)@.dom().len() >= k__pre_self__l3_tables___dom___lenrng_lo && (pre_self_.l3_tables)@.dom().len() <= k__pre_self__l3_tables___dom___lenrng_hi); }
    if g__pre_self__l3_tables___dom___contains { assume((pre_self_.l3_tables)@.dom().contains(k__pre_self__l3_tables___dom___contains)); }
    if g__pre_self__l2_rev_map___dom___empty { assume((pre_self_.l2_rev_map)@.dom() == Set::<PageMapPtr>::empty()); }
    if g__pre_self__l2_rev_map___dom___lengt { assume((pre_self_.l2_rev_map)@.dom().len() > 0); }
    if g__pre_self__l2_rev_map___dom___leneq { assume((pre_self_.l2_rev_map)@.dom().len() == k__pre_self__l2_rev_map___dom___leneq); }
    if g__pre_self__l2_rev_map___dom___lenrng { assume((pre_self_.l2_rev_map)@.dom().len() >= k__pre_self__l2_rev_map___dom___lenrng_lo && (pre_self_.l2_rev_map)@.dom().len() <= k__pre_self__l2_rev_map___dom___lenrng_hi); }
    if g__pre_self__l2_rev_map___dom___contains { assume((pre_self_.l2_rev_map)@.dom().contains(k__pre_self__l2_rev_map___dom___contains)); }
    if g__pre_self__l2_tables___dom___empty { assume((pre_self_.l2_tables)@.dom() == Set::<PageMapPtr>::empty()); }
    if g__pre_self__l2_tables___dom___lengt { assume((pre_self_.l2_tables)@.dom().len() > 0); }
    if g__pre_self__l2_tables___dom___leneq { assume((pre_self_.l2_tables)@.dom().len() == k__pre_self__l2_tables___dom___leneq); }
    if g__pre_self__l2_tables___dom___lenrng { assume((pre_self_.l2_tables)@.dom().len() >= k__pre_self__l2_tables___dom___lenrng_lo && (pre_self_.l2_tables)@.dom().len() <= k__pre_self__l2_tables___dom___lenrng_hi); }
    if g__pre_self__l2_tables___dom___contains { assume((pre_self_.l2_tables)@.dom().contains(k__pre_self__l2_tables___dom___contains)); }
    if g__pre_self__l1_rev_map___dom___empty { assume((pre_self_.l1_rev_map)@.dom() == Set::<PageMapPtr>::empty()); }
    if g__pre_self__l1_rev_map___dom___lengt { assume((pre_self_.l1_rev_map)@.dom().len() > 0); }
    if g__pre_self__l1_rev_map___dom___leneq { assume((pre_self_.l1_rev_map)@.dom().len() == k__pre_self__l1_rev_map___dom___leneq); }
    if g__pre_self__l1_rev_map___dom___lenrng { assume((pre_self_.l1_rev_map)@.dom().len() >= k__pre_self__l1_rev_map___dom___lenrng_lo && (pre_self_.l1_rev_map)@.dom().len() <= k__pre_self__l1_rev_map___dom___lenrng_hi); }
    if g__pre_self__l1_rev_map___dom___contains { assume((pre_self_.l1_rev_map)@.dom().contains(k__pre_self__l1_rev_map___dom___contains)); }
    if g__pre_self__l1_tables___dom___empty { assume((pre_self_.l1_tables)@.dom() == Set::<PageMapPtr>::empty()); }
    if g__pre_self__l1_tables___dom___lengt { assume((pre_self_.l1_tables)@.dom().len() > 0); }
    if g__pre_self__l1_tables___dom___leneq { assume((pre_self_.l1_tables)@.dom().len() == k__pre_self__l1_tables___dom___leneq); }
    if g__pre_self__l1_tables___dom___lenrng { assume((pre_self_.l1_tables)@.dom().len() >= k__pre_self__l1_tables___dom___lenrng_lo && (pre_self_.l1_tables)@.dom().len() <= k__pre_self__l1_tables___dom___lenrng_hi); }
    if g__pre_self__l1_tables___dom___contains { assume((pre_self_.l1_tables)@.dom().contains(k__pre_self__l1_tables___dom___contains)); }
    if g__pre_self__mapping_4k___dom___empty { assume((pre_self_.mapping_4k)@.dom() == Set::<VAddr>::empty()); }
    if g__pre_self__mapping_4k___dom___lengt { assume((pre_self_.mapping_4k)@.dom().len() > 0); }
    if g__pre_self__mapping_4k___dom___leneq { assume((pre_self_.mapping_4k)@.dom().len() == k__pre_self__mapping_4k___dom___leneq); }
    if g__pre_self__mapping_4k___dom___lenrng { assume((pre_self_.mapping_4k)@.dom().len() >= k__pre_self__mapping_4k___dom___lenrng_lo && (pre_self_.mapping_4k)@.dom().len() <= k__pre_self__mapping_4k___dom___lenrng_hi); }
    if g__pre_self__mapping_4k___dom___contains { assume((pre_self_.mapping_4k)@.dom().contains(k__pre_self__mapping_4k___dom___contains)); }
    if g__pre_self__mapping_2m___dom___empty { assume((pre_self_.mapping_2m)@.dom() == Set::<VAddr>::empty()); }
    if g__pre_self__mapping_2m___dom___lengt { assume((pre_self_.mapping_2m)@.dom().len() > 0); }
    if g__pre_self__mapping_2m___dom___leneq { assume((pre_self_.mapping_2m)@.dom().len() == k__pre_self__mapping_2m___dom___leneq); }
    if g__pre_self__mapping_2m___dom___lenrng { assume((pre_self_.mapping_2m)@.dom().len() >= k__pre_self__mapping_2m___dom___lenrng_lo && (pre_self_.mapping_2m)@.dom().len() <= k__pre_self__mapping_2m___dom___lenrng_hi); }
    if g__pre_self__mapping_2m___dom___contains { assume((pre_self_.mapping_2m)@.dom().contains(k__pre_self__mapping_2m___dom___contains)); }
    if g__pre_self__mapping_1g___dom___empty { assume((pre_self_.mapping_1g)@.dom() == Set::<VAddr>::empty()); }
    if g__pre_self__mapping_1g___dom___lengt { assume((pre_self_.mapping_1g)@.dom().len() > 0); }
    if g__pre_self__mapping_1g___dom___leneq { assume((pre_self_.mapping_1g)@.dom().len() == k__pre_self__mapping_1g___dom___leneq); }
    if g__pre_self__mapping_1g___dom___lenrng { assume((pre_self_.mapping_1g)@.dom().len() >= k__pre_self__mapping_1g___dom___lenrng_lo && (pre_self_.mapping_1g)@.dom().len() <= k__pre_self__mapping_1g___dom___lenrng_hi); }
    if g__pre_self__mapping_1g___dom___contains { assume((pre_self_.mapping_1g)@.dom().contains(k__pre_self__mapping_1g___dom___contains)); }
    if g__pre_self__kernel_entries___leneq { assume((pre_self_.kernel_entries)@.len() == k__pre_self__kernel_entries___leneq); }
    if g__pre_self__kernel_entries___lenrng { assume((pre_self_.kernel_entries)@.len() >= k__pre_self__kernel_entries___lenrng_lo && (pre_self_.kernel_entries)@.len() <= k__pre_self__kernel_entries___lenrng_hi); }
    if g__pre_self__kernel_entries___0__perm_present_is_true { assume((pre_self_.kernel_entries)@[0].perm.present == true); }
    if g__pre_self__kernel_entries___0__perm_present_is_false { assume((pre_self_.kernel_entries)@[0].perm.present == false); }
    if g__pre_self__kernel_entries___0__perm_ps_is_true { assume((pre_self_.kernel_entries)@[0].perm.ps == true); }
    if g__pre_self__kernel_entries___0__perm_ps_is_false { assume((pre_self_.kernel_entries)@[0].perm.ps == false); }
    if g__pre_self__kernel_entries___0__perm_write_is_true { assume((pre_self_.kernel_entries)@[0].perm.write == true); }
    if g__pre_self__kernel_entries___0__perm_write_is_false { assume((pre_self_.kernel_entries)@[0].perm.write == false); }
    if g__pre_self__kernel_entries___0__perm_execute_disable_is_true { assume((pre_self_.kernel_entries)@[0].perm.execute_disable == true); }
    if g__pre_self__kernel_entries___0__perm_execute_disable_is_false { assume((pre_self_.kernel_entries)@[0].perm.execute_disable == false); }
    if g__pre_self__kernel_entries___0__perm_user_is_true { assume((pre_self_.kernel_entries)@[0].perm.user == true); }
    if g__pre_self__kernel_entries___0__perm_user_is_false { assume((pre_self_.kernel_entries)@[0].perm.user == false); }
    if g__pre_self__kernel_entries___1__perm_present_is_true { assume((pre_self_.kernel_entries)@[1].perm.present == true); }
    if g__pre_self__kernel_entries___1__perm_present_is_false { assume((pre_self_.kernel_entries)@[1].perm.present == false); }
    if g__pre_self__kernel_entries___1__perm_ps_is_true { assume((pre_self_.kernel_entries)@[1].perm.ps == true); }
    if g__pre_self__kernel_entries___1__perm_ps_is_false { assume((pre_self_.kernel_entries)@[1].perm.ps == false); }
    if g__pre_self__kernel_entries___1__perm_write_is_true { assume((pre_self_.kernel_entries)@[1].perm.write == true); }
    if g__pre_self__kernel_entries___1__perm_write_is_false { assume((pre_self_.kernel_entries)@[1].perm.write == false); }
    if g__pre_self__kernel_entries___1__perm_execute_disable_is_true { assume((pre_self_.kernel_entries)@[1].perm.execute_disable == true); }
    if g__pre_self__kernel_entries___1__perm_execute_disable_is_false { assume((pre_self_.kernel_entries)@[1].perm.execute_disable == false); }
    if g__pre_self__kernel_entries___1__perm_user_is_true { assume((pre_self_.kernel_entries)@[1].perm.user == true); }
    if g__pre_self__kernel_entries___1__perm_user_is_false { assume((pre_self_.kernel_entries)@[1].perm.user == false); }
    if g__pre_self__kernel_entries___2__perm_present_is_true { assume((pre_self_.kernel_entries)@[2].perm.present == true); }
    if g__pre_self__kernel_entries___2__perm_present_is_false { assume((pre_self_.kernel_entries)@[2].perm.present == false); }
    if g__pre_self__kernel_entries___2__perm_ps_is_true { assume((pre_self_.kernel_entries)@[2].perm.ps == true); }
    if g__pre_self__kernel_entries___2__perm_ps_is_false { assume((pre_self_.kernel_entries)@[2].perm.ps == false); }
    if g__pre_self__kernel_entries___2__perm_write_is_true { assume((pre_self_.kernel_entries)@[2].perm.write == true); }
    if g__pre_self__kernel_entries___2__perm_write_is_false { assume((pre_self_.kernel_entries)@[2].perm.write == false); }
    if g__pre_self__kernel_entries___2__perm_execute_disable_is_true { assume((pre_self_.kernel_entries)@[2].perm.execute_disable == true); }
    if g__pre_self__kernel_entries___2__perm_execute_disable_is_false { assume((pre_self_.kernel_entries)@[2].perm.execute_disable == false); }
    if g__pre_self__kernel_entries___2__perm_user_is_true { assume((pre_self_.kernel_entries)@[2].perm.user == true); }
    if g__pre_self__kernel_entries___2__perm_user_is_false { assume((pre_self_.kernel_entries)@[2].perm.user == false); }
    if g__pre_self__kernel_entries___3__perm_present_is_true { assume((pre_self_.kernel_entries)@[3].perm.present == true); }
    if g__pre_self__kernel_entries___3__perm_present_is_false { assume((pre_self_.kernel_entries)@[3].perm.present == false); }
    if g__pre_self__kernel_entries___3__perm_ps_is_true { assume((pre_self_.kernel_entries)@[3].perm.ps == true); }
    if g__pre_self__kernel_entries___3__perm_ps_is_false { assume((pre_self_.kernel_entries)@[3].perm.ps == false); }
    if g__pre_self__kernel_entries___3__perm_write_is_true { assume((pre_self_.kernel_entries)@[3].perm.write == true); }
    if g__pre_self__kernel_entries___3__perm_write_is_false { assume((pre_self_.kernel_entries)@[3].perm.write == false); }
    if g__pre_self__kernel_entries___3__perm_execute_disable_is_true { assume((pre_self_.kernel_entries)@[3].perm.execute_disable == true); }
    if g__pre_self__kernel_entries___3__perm_execute_disable_is_false { assume((pre_self_.kernel_entries)@[3].perm.execute_disable == false); }
    if g__pre_self__kernel_entries___3__perm_user_is_true { assume((pre_self_.kernel_entries)@[3].perm.user == true); }
    if g__pre_self__kernel_entries___3__perm_user_is_false { assume((pre_self_.kernel_entries)@[3].perm.user == false); }
    if g__pre_self__kernel_entries___4__perm_present_is_true { assume((pre_self_.kernel_entries)@[4].perm.present == true); }
    if g__pre_self__kernel_entries___4__perm_present_is_false { assume((pre_self_.kernel_entries)@[4].perm.present == false); }
    if g__pre_self__kernel_entries___4__perm_ps_is_true { assume((pre_self_.kernel_entries)@[4].perm.ps == true); }
    if g__pre_self__kernel_entries___4__perm_ps_is_false { assume((pre_self_.kernel_entries)@[4].perm.ps == false); }
    if g__pre_self__kernel_entries___4__perm_write_is_true { assume((pre_self_.kernel_entries)@[4].perm.write == true); }
    if g__pre_self__kernel_entries___4__perm_write_is_false { assume((pre_self_.kernel_entries)@[4].perm.write == false); }
    if g__pre_self__kernel_entries___4__perm_execute_disable_is_true { assume((pre_self_.kernel_entries)@[4].perm.execute_disable == true); }
    if g__pre_self__kernel_entries___4__perm_execute_disable_is_false { assume((pre_self_.kernel_entries)@[4].perm.execute_disable == false); }
    if g__pre_self__kernel_entries___4__perm_user_is_true { assume((pre_self_.kernel_entries)@[4].perm.user == true); }
    if g__pre_self__kernel_entries___4__perm_user_is_false { assume((pre_self_.kernel_entries)@[4].perm.user == false); }
    if g__pre_self__kernel_entries___5__perm_present_is_true { assume((pre_self_.kernel_entries)@[5].perm.present == true); }
    if g__pre_self__kernel_entries___5__perm_present_is_false { assume((pre_self_.kernel_entries)@[5].perm.present == false); }
    if g__pre_self__kernel_entries___5__perm_ps_is_true { assume((pre_self_.kernel_entries)@[5].perm.ps == true); }
    if g__pre_self__kernel_entries___5__perm_ps_is_false { assume((pre_self_.kernel_entries)@[5].perm.ps == false); }
    if g__pre_self__kernel_entries___5__perm_write_is_true { assume((pre_self_.kernel_entries)@[5].perm.write == true); }
    if g__pre_self__kernel_entries___5__perm_write_is_false { assume((pre_self_.kernel_entries)@[5].perm.write == false); }
    if g__pre_self__kernel_entries___5__perm_execute_disable_is_true { assume((pre_self_.kernel_entries)@[5].perm.execute_disable == true); }
    if g__pre_self__kernel_entries___5__perm_execute_disable_is_false { assume((pre_self_.kernel_entries)@[5].perm.execute_disable == false); }
    if g__pre_self__kernel_entries___5__perm_user_is_true { assume((pre_self_.kernel_entries)@[5].perm.user == true); }
    if g__pre_self__kernel_entries___5__perm_user_is_false { assume((pre_self_.kernel_entries)@[5].perm.user == false); }
    if g__pre_self__kernel_entries___6__perm_present_is_true { assume((pre_self_.kernel_entries)@[6].perm.present == true); }
    if g__pre_self__kernel_entries___6__perm_present_is_false { assume((pre_self_.kernel_entries)@[6].perm.present == false); }
    if g__pre_self__kernel_entries___6__perm_ps_is_true { assume((pre_self_.kernel_entries)@[6].perm.ps == true); }
    if g__pre_self__kernel_entries___6__perm_ps_is_false { assume((pre_self_.kernel_entries)@[6].perm.ps == false); }
    if g__pre_self__kernel_entries___6__perm_write_is_true { assume((pre_self_.kernel_entries)@[6].perm.write == true); }
    if g__pre_self__kernel_entries___6__perm_write_is_false { assume((pre_self_.kernel_entries)@[6].perm.write == false); }
    if g__pre_self__kernel_entries___6__perm_execute_disable_is_true { assume((pre_self_.kernel_entries)@[6].perm.execute_disable == true); }
    if g__pre_self__kernel_entries___6__perm_execute_disable_is_false { assume((pre_self_.kernel_entries)@[6].perm.execute_disable == false); }
    if g__pre_self__kernel_entries___6__perm_user_is_true { assume((pre_self_.kernel_entries)@[6].perm.user == true); }
    if g__pre_self__kernel_entries___6__perm_user_is_false { assume((pre_self_.kernel_entries)@[6].perm.user == false); }
    if g__pre_self__kernel_entries___7__perm_present_is_true { assume((pre_self_.kernel_entries)@[7].perm.present == true); }
    if g__pre_self__kernel_entries___7__perm_present_is_false { assume((pre_self_.kernel_entries)@[7].perm.present == false); }
    if g__pre_self__kernel_entries___7__perm_ps_is_true { assume((pre_self_.kernel_entries)@[7].perm.ps == true); }
    if g__pre_self__kernel_entries___7__perm_ps_is_false { assume((pre_self_.kernel_entries)@[7].perm.ps == false); }
    if g__pre_self__kernel_entries___7__perm_write_is_true { assume((pre_self_.kernel_entries)@[7].perm.write == true); }
    if g__pre_self__kernel_entries___7__perm_write_is_false { assume((pre_self_.kernel_entries)@[7].perm.write == false); }
    if g__pre_self__kernel_entries___7__perm_execute_disable_is_true { assume((pre_self_.kernel_entries)@[7].perm.execute_disable == true); }
    if g__pre_self__kernel_entries___7__perm_execute_disable_is_false { assume((pre_self_.kernel_entries)@[7].perm.execute_disable == false); }
    if g__pre_self__kernel_entries___7__perm_user_is_true { assume((pre_self_.kernel_entries)@[7].perm.user == true); }
    if g__pre_self__kernel_entries___7__perm_user_is_false { assume((pre_self_.kernel_entries)@[7].perm.user == false); }
    if g__pre_self__tlb_mapping_4k___leneq { assume((pre_self_.tlb_mapping_4k)@.len() == k__pre_self__tlb_mapping_4k___leneq); }
    if g__pre_self__tlb_mapping_4k___lenrng { assume((pre_self_.tlb_mapping_4k)@.len() >= k__pre_self__tlb_mapping_4k___lenrng_lo && (pre_self_.tlb_mapping_4k)@.len() <= k__pre_self__tlb_mapping_4k___lenrng_hi); }
    if g__pre_self__tlb_mapping_4k___0__dom___empty { assume((pre_self_.tlb_mapping_4k)@[0].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_4k___0__dom___lengt { assume((pre_self_.tlb_mapping_4k)@[0].dom().len() > 0); }
    if g__pre_self__tlb_mapping_4k___0__dom___leneq { assume((pre_self_.tlb_mapping_4k)@[0].dom().len() == k__pre_self__tlb_mapping_4k___0__dom___leneq); }
    if g__pre_self__tlb_mapping_4k___0__dom___lenrng { assume((pre_self_.tlb_mapping_4k)@[0].dom().len() >= k__pre_self__tlb_mapping_4k___0__dom___lenrng_lo && (pre_self_.tlb_mapping_4k)@[0].dom().len() <= k__pre_self__tlb_mapping_4k___0__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_4k___0__dom___contains { assume((pre_self_.tlb_mapping_4k)@[0].dom().contains(k__pre_self__tlb_mapping_4k___0__dom___contains)); }
    if g__pre_self__tlb_mapping_4k___1__dom___empty { assume((pre_self_.tlb_mapping_4k)@[1].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_4k___1__dom___lengt { assume((pre_self_.tlb_mapping_4k)@[1].dom().len() > 0); }
    if g__pre_self__tlb_mapping_4k___1__dom___leneq { assume((pre_self_.tlb_mapping_4k)@[1].dom().len() == k__pre_self__tlb_mapping_4k___1__dom___leneq); }
    if g__pre_self__tlb_mapping_4k___1__dom___lenrng { assume((pre_self_.tlb_mapping_4k)@[1].dom().len() >= k__pre_self__tlb_mapping_4k___1__dom___lenrng_lo && (pre_self_.tlb_mapping_4k)@[1].dom().len() <= k__pre_self__tlb_mapping_4k___1__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_4k___1__dom___contains { assume((pre_self_.tlb_mapping_4k)@[1].dom().contains(k__pre_self__tlb_mapping_4k___1__dom___contains)); }
    if g__pre_self__tlb_mapping_4k___2__dom___empty { assume((pre_self_.tlb_mapping_4k)@[2].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_4k___2__dom___lengt { assume((pre_self_.tlb_mapping_4k)@[2].dom().len() > 0); }
    if g__pre_self__tlb_mapping_4k___2__dom___leneq { assume((pre_self_.tlb_mapping_4k)@[2].dom().len() == k__pre_self__tlb_mapping_4k___2__dom___leneq); }
    if g__pre_self__tlb_mapping_4k___2__dom___lenrng { assume((pre_self_.tlb_mapping_4k)@[2].dom().len() >= k__pre_self__tlb_mapping_4k___2__dom___lenrng_lo && (pre_self_.tlb_mapping_4k)@[2].dom().len() <= k__pre_self__tlb_mapping_4k___2__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_4k___2__dom___contains { assume((pre_self_.tlb_mapping_4k)@[2].dom().contains(k__pre_self__tlb_mapping_4k___2__dom___contains)); }
    if g__pre_self__tlb_mapping_4k___3__dom___empty { assume((pre_self_.tlb_mapping_4k)@[3].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_4k___3__dom___lengt { assume((pre_self_.tlb_mapping_4k)@[3].dom().len() > 0); }
    if g__pre_self__tlb_mapping_4k___3__dom___leneq { assume((pre_self_.tlb_mapping_4k)@[3].dom().len() == k__pre_self__tlb_mapping_4k___3__dom___leneq); }
    if g__pre_self__tlb_mapping_4k___3__dom___lenrng { assume((pre_self_.tlb_mapping_4k)@[3].dom().len() >= k__pre_self__tlb_mapping_4k___3__dom___lenrng_lo && (pre_self_.tlb_mapping_4k)@[3].dom().len() <= k__pre_self__tlb_mapping_4k___3__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_4k___3__dom___contains { assume((pre_self_.tlb_mapping_4k)@[3].dom().contains(k__pre_self__tlb_mapping_4k___3__dom___contains)); }
    if g__pre_self__tlb_mapping_4k___4__dom___empty { assume((pre_self_.tlb_mapping_4k)@[4].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_4k___4__dom___lengt { assume((pre_self_.tlb_mapping_4k)@[4].dom().len() > 0); }
    if g__pre_self__tlb_mapping_4k___4__dom___leneq { assume((pre_self_.tlb_mapping_4k)@[4].dom().len() == k__pre_self__tlb_mapping_4k___4__dom___leneq); }
    if g__pre_self__tlb_mapping_4k___4__dom___lenrng { assume((pre_self_.tlb_mapping_4k)@[4].dom().len() >= k__pre_self__tlb_mapping_4k___4__dom___lenrng_lo && (pre_self_.tlb_mapping_4k)@[4].dom().len() <= k__pre_self__tlb_mapping_4k___4__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_4k___4__dom___contains { assume((pre_self_.tlb_mapping_4k)@[4].dom().contains(k__pre_self__tlb_mapping_4k___4__dom___contains)); }
    if g__pre_self__tlb_mapping_4k___5__dom___empty { assume((pre_self_.tlb_mapping_4k)@[5].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_4k___5__dom___lengt { assume((pre_self_.tlb_mapping_4k)@[5].dom().len() > 0); }
    if g__pre_self__tlb_mapping_4k___5__dom___leneq { assume((pre_self_.tlb_mapping_4k)@[5].dom().len() == k__pre_self__tlb_mapping_4k___5__dom___leneq); }
    if g__pre_self__tlb_mapping_4k___5__dom___lenrng { assume((pre_self_.tlb_mapping_4k)@[5].dom().len() >= k__pre_self__tlb_mapping_4k___5__dom___lenrng_lo && (pre_self_.tlb_mapping_4k)@[5].dom().len() <= k__pre_self__tlb_mapping_4k___5__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_4k___5__dom___contains { assume((pre_self_.tlb_mapping_4k)@[5].dom().contains(k__pre_self__tlb_mapping_4k___5__dom___contains)); }
    if g__pre_self__tlb_mapping_4k___6__dom___empty { assume((pre_self_.tlb_mapping_4k)@[6].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_4k___6__dom___lengt { assume((pre_self_.tlb_mapping_4k)@[6].dom().len() > 0); }
    if g__pre_self__tlb_mapping_4k___6__dom___leneq { assume((pre_self_.tlb_mapping_4k)@[6].dom().len() == k__pre_self__tlb_mapping_4k___6__dom___leneq); }
    if g__pre_self__tlb_mapping_4k___6__dom___lenrng { assume((pre_self_.tlb_mapping_4k)@[6].dom().len() >= k__pre_self__tlb_mapping_4k___6__dom___lenrng_lo && (pre_self_.tlb_mapping_4k)@[6].dom().len() <= k__pre_self__tlb_mapping_4k___6__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_4k___6__dom___contains { assume((pre_self_.tlb_mapping_4k)@[6].dom().contains(k__pre_self__tlb_mapping_4k___6__dom___contains)); }
    if g__pre_self__tlb_mapping_4k___7__dom___empty { assume((pre_self_.tlb_mapping_4k)@[7].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_4k___7__dom___lengt { assume((pre_self_.tlb_mapping_4k)@[7].dom().len() > 0); }
    if g__pre_self__tlb_mapping_4k___7__dom___leneq { assume((pre_self_.tlb_mapping_4k)@[7].dom().len() == k__pre_self__tlb_mapping_4k___7__dom___leneq); }
    if g__pre_self__tlb_mapping_4k___7__dom___lenrng { assume((pre_self_.tlb_mapping_4k)@[7].dom().len() >= k__pre_self__tlb_mapping_4k___7__dom___lenrng_lo && (pre_self_.tlb_mapping_4k)@[7].dom().len() <= k__pre_self__tlb_mapping_4k___7__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_4k___7__dom___contains { assume((pre_self_.tlb_mapping_4k)@[7].dom().contains(k__pre_self__tlb_mapping_4k___7__dom___contains)); }
    if g__pre_self__tlb_mapping_2m___leneq { assume((pre_self_.tlb_mapping_2m)@.len() == k__pre_self__tlb_mapping_2m___leneq); }
    if g__pre_self__tlb_mapping_2m___lenrng { assume((pre_self_.tlb_mapping_2m)@.len() >= k__pre_self__tlb_mapping_2m___lenrng_lo && (pre_self_.tlb_mapping_2m)@.len() <= k__pre_self__tlb_mapping_2m___lenrng_hi); }
    if g__pre_self__tlb_mapping_2m___0__dom___empty { assume((pre_self_.tlb_mapping_2m)@[0].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_2m___0__dom___lengt { assume((pre_self_.tlb_mapping_2m)@[0].dom().len() > 0); }
    if g__pre_self__tlb_mapping_2m___0__dom___leneq { assume((pre_self_.tlb_mapping_2m)@[0].dom().len() == k__pre_self__tlb_mapping_2m___0__dom___leneq); }
    if g__pre_self__tlb_mapping_2m___0__dom___lenrng { assume((pre_self_.tlb_mapping_2m)@[0].dom().len() >= k__pre_self__tlb_mapping_2m___0__dom___lenrng_lo && (pre_self_.tlb_mapping_2m)@[0].dom().len() <= k__pre_self__tlb_mapping_2m___0__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_2m___0__dom___contains { assume((pre_self_.tlb_mapping_2m)@[0].dom().contains(k__pre_self__tlb_mapping_2m___0__dom___contains)); }
    if g__pre_self__tlb_mapping_2m___1__dom___empty { assume((pre_self_.tlb_mapping_2m)@[1].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_2m___1__dom___lengt { assume((pre_self_.tlb_mapping_2m)@[1].dom().len() > 0); }
    if g__pre_self__tlb_mapping_2m___1__dom___leneq { assume((pre_self_.tlb_mapping_2m)@[1].dom().len() == k__pre_self__tlb_mapping_2m___1__dom___leneq); }
    if g__pre_self__tlb_mapping_2m___1__dom___lenrng { assume((pre_self_.tlb_mapping_2m)@[1].dom().len() >= k__pre_self__tlb_mapping_2m___1__dom___lenrng_lo && (pre_self_.tlb_mapping_2m)@[1].dom().len() <= k__pre_self__tlb_mapping_2m___1__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_2m___1__dom___contains { assume((pre_self_.tlb_mapping_2m)@[1].dom().contains(k__pre_self__tlb_mapping_2m___1__dom___contains)); }
    if g__pre_self__tlb_mapping_2m___2__dom___empty { assume((pre_self_.tlb_mapping_2m)@[2].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_2m___2__dom___lengt { assume((pre_self_.tlb_mapping_2m)@[2].dom().len() > 0); }
    if g__pre_self__tlb_mapping_2m___2__dom___leneq { assume((pre_self_.tlb_mapping_2m)@[2].dom().len() == k__pre_self__tlb_mapping_2m___2__dom___leneq); }
    if g__pre_self__tlb_mapping_2m___2__dom___lenrng { assume((pre_self_.tlb_mapping_2m)@[2].dom().len() >= k__pre_self__tlb_mapping_2m___2__dom___lenrng_lo && (pre_self_.tlb_mapping_2m)@[2].dom().len() <= k__pre_self__tlb_mapping_2m___2__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_2m___2__dom___contains { assume((pre_self_.tlb_mapping_2m)@[2].dom().contains(k__pre_self__tlb_mapping_2m___2__dom___contains)); }
    if g__pre_self__tlb_mapping_2m___3__dom___empty { assume((pre_self_.tlb_mapping_2m)@[3].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_2m___3__dom___lengt { assume((pre_self_.tlb_mapping_2m)@[3].dom().len() > 0); }
    if g__pre_self__tlb_mapping_2m___3__dom___leneq { assume((pre_self_.tlb_mapping_2m)@[3].dom().len() == k__pre_self__tlb_mapping_2m___3__dom___leneq); }
    if g__pre_self__tlb_mapping_2m___3__dom___lenrng { assume((pre_self_.tlb_mapping_2m)@[3].dom().len() >= k__pre_self__tlb_mapping_2m___3__dom___lenrng_lo && (pre_self_.tlb_mapping_2m)@[3].dom().len() <= k__pre_self__tlb_mapping_2m___3__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_2m___3__dom___contains { assume((pre_self_.tlb_mapping_2m)@[3].dom().contains(k__pre_self__tlb_mapping_2m___3__dom___contains)); }
    if g__pre_self__tlb_mapping_2m___4__dom___empty { assume((pre_self_.tlb_mapping_2m)@[4].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_2m___4__dom___lengt { assume((pre_self_.tlb_mapping_2m)@[4].dom().len() > 0); }
    if g__pre_self__tlb_mapping_2m___4__dom___leneq { assume((pre_self_.tlb_mapping_2m)@[4].dom().len() == k__pre_self__tlb_mapping_2m___4__dom___leneq); }
    if g__pre_self__tlb_mapping_2m___4__dom___lenrng { assume((pre_self_.tlb_mapping_2m)@[4].dom().len() >= k__pre_self__tlb_mapping_2m___4__dom___lenrng_lo && (pre_self_.tlb_mapping_2m)@[4].dom().len() <= k__pre_self__tlb_mapping_2m___4__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_2m___4__dom___contains { assume((pre_self_.tlb_mapping_2m)@[4].dom().contains(k__pre_self__tlb_mapping_2m___4__dom___contains)); }
    if g__pre_self__tlb_mapping_2m___5__dom___empty { assume((pre_self_.tlb_mapping_2m)@[5].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_2m___5__dom___lengt { assume((pre_self_.tlb_mapping_2m)@[5].dom().len() > 0); }
    if g__pre_self__tlb_mapping_2m___5__dom___leneq { assume((pre_self_.tlb_mapping_2m)@[5].dom().len() == k__pre_self__tlb_mapping_2m___5__dom___leneq); }
    if g__pre_self__tlb_mapping_2m___5__dom___lenrng { assume((pre_self_.tlb_mapping_2m)@[5].dom().len() >= k__pre_self__tlb_mapping_2m___5__dom___lenrng_lo && (pre_self_.tlb_mapping_2m)@[5].dom().len() <= k__pre_self__tlb_mapping_2m___5__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_2m___5__dom___contains { assume((pre_self_.tlb_mapping_2m)@[5].dom().contains(k__pre_self__tlb_mapping_2m___5__dom___contains)); }
    if g__pre_self__tlb_mapping_2m___6__dom___empty { assume((pre_self_.tlb_mapping_2m)@[6].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_2m___6__dom___lengt { assume((pre_self_.tlb_mapping_2m)@[6].dom().len() > 0); }
    if g__pre_self__tlb_mapping_2m___6__dom___leneq { assume((pre_self_.tlb_mapping_2m)@[6].dom().len() == k__pre_self__tlb_mapping_2m___6__dom___leneq); }
    if g__pre_self__tlb_mapping_2m___6__dom___lenrng { assume((pre_self_.tlb_mapping_2m)@[6].dom().len() >= k__pre_self__tlb_mapping_2m___6__dom___lenrng_lo && (pre_self_.tlb_mapping_2m)@[6].dom().len() <= k__pre_self__tlb_mapping_2m___6__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_2m___6__dom___contains { assume((pre_self_.tlb_mapping_2m)@[6].dom().contains(k__pre_self__tlb_mapping_2m___6__dom___contains)); }
    if g__pre_self__tlb_mapping_2m___7__dom___empty { assume((pre_self_.tlb_mapping_2m)@[7].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_2m___7__dom___lengt { assume((pre_self_.tlb_mapping_2m)@[7].dom().len() > 0); }
    if g__pre_self__tlb_mapping_2m___7__dom___leneq { assume((pre_self_.tlb_mapping_2m)@[7].dom().len() == k__pre_self__tlb_mapping_2m___7__dom___leneq); }
    if g__pre_self__tlb_mapping_2m___7__dom___lenrng { assume((pre_self_.tlb_mapping_2m)@[7].dom().len() >= k__pre_self__tlb_mapping_2m___7__dom___lenrng_lo && (pre_self_.tlb_mapping_2m)@[7].dom().len() <= k__pre_self__tlb_mapping_2m___7__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_2m___7__dom___contains { assume((pre_self_.tlb_mapping_2m)@[7].dom().contains(k__pre_self__tlb_mapping_2m___7__dom___contains)); }
    if g__pre_self__tlb_mapping_1g___leneq { assume((pre_self_.tlb_mapping_1g)@.len() == k__pre_self__tlb_mapping_1g___leneq); }
    if g__pre_self__tlb_mapping_1g___lenrng { assume((pre_self_.tlb_mapping_1g)@.len() >= k__pre_self__tlb_mapping_1g___lenrng_lo && (pre_self_.tlb_mapping_1g)@.len() <= k__pre_self__tlb_mapping_1g___lenrng_hi); }
    if g__pre_self__tlb_mapping_1g___0__dom___empty { assume((pre_self_.tlb_mapping_1g)@[0].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_1g___0__dom___lengt { assume((pre_self_.tlb_mapping_1g)@[0].dom().len() > 0); }
    if g__pre_self__tlb_mapping_1g___0__dom___leneq { assume((pre_self_.tlb_mapping_1g)@[0].dom().len() == k__pre_self__tlb_mapping_1g___0__dom___leneq); }
    if g__pre_self__tlb_mapping_1g___0__dom___lenrng { assume((pre_self_.tlb_mapping_1g)@[0].dom().len() >= k__pre_self__tlb_mapping_1g___0__dom___lenrng_lo && (pre_self_.tlb_mapping_1g)@[0].dom().len() <= k__pre_self__tlb_mapping_1g___0__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_1g___0__dom___contains { assume((pre_self_.tlb_mapping_1g)@[0].dom().contains(k__pre_self__tlb_mapping_1g___0__dom___contains)); }
    if g__pre_self__tlb_mapping_1g___1__dom___empty { assume((pre_self_.tlb_mapping_1g)@[1].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_1g___1__dom___lengt { assume((pre_self_.tlb_mapping_1g)@[1].dom().len() > 0); }
    if g__pre_self__tlb_mapping_1g___1__dom___leneq { assume((pre_self_.tlb_mapping_1g)@[1].dom().len() == k__pre_self__tlb_mapping_1g___1__dom___leneq); }
    if g__pre_self__tlb_mapping_1g___1__dom___lenrng { assume((pre_self_.tlb_mapping_1g)@[1].dom().len() >= k__pre_self__tlb_mapping_1g___1__dom___lenrng_lo && (pre_self_.tlb_mapping_1g)@[1].dom().len() <= k__pre_self__tlb_mapping_1g___1__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_1g___1__dom___contains { assume((pre_self_.tlb_mapping_1g)@[1].dom().contains(k__pre_self__tlb_mapping_1g___1__dom___contains)); }
    if g__pre_self__tlb_mapping_1g___2__dom___empty { assume((pre_self_.tlb_mapping_1g)@[2].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_1g___2__dom___lengt { assume((pre_self_.tlb_mapping_1g)@[2].dom().len() > 0); }
    if g__pre_self__tlb_mapping_1g___2__dom___leneq { assume((pre_self_.tlb_mapping_1g)@[2].dom().len() == k__pre_self__tlb_mapping_1g___2__dom___leneq); }
    if g__pre_self__tlb_mapping_1g___2__dom___lenrng { assume((pre_self_.tlb_mapping_1g)@[2].dom().len() >= k__pre_self__tlb_mapping_1g___2__dom___lenrng_lo && (pre_self_.tlb_mapping_1g)@[2].dom().len() <= k__pre_self__tlb_mapping_1g___2__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_1g___2__dom___contains { assume((pre_self_.tlb_mapping_1g)@[2].dom().contains(k__pre_self__tlb_mapping_1g___2__dom___contains)); }
    if g__pre_self__tlb_mapping_1g___3__dom___empty { assume((pre_self_.tlb_mapping_1g)@[3].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_1g___3__dom___lengt { assume((pre_self_.tlb_mapping_1g)@[3].dom().len() > 0); }
    if g__pre_self__tlb_mapping_1g___3__dom___leneq { assume((pre_self_.tlb_mapping_1g)@[3].dom().len() == k__pre_self__tlb_mapping_1g___3__dom___leneq); }
    if g__pre_self__tlb_mapping_1g___3__dom___lenrng { assume((pre_self_.tlb_mapping_1g)@[3].dom().len() >= k__pre_self__tlb_mapping_1g___3__dom___lenrng_lo && (pre_self_.tlb_mapping_1g)@[3].dom().len() <= k__pre_self__tlb_mapping_1g___3__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_1g___3__dom___contains { assume((pre_self_.tlb_mapping_1g)@[3].dom().contains(k__pre_self__tlb_mapping_1g___3__dom___contains)); }
    if g__pre_self__tlb_mapping_1g___4__dom___empty { assume((pre_self_.tlb_mapping_1g)@[4].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_1g___4__dom___lengt { assume((pre_self_.tlb_mapping_1g)@[4].dom().len() > 0); }
    if g__pre_self__tlb_mapping_1g___4__dom___leneq { assume((pre_self_.tlb_mapping_1g)@[4].dom().len() == k__pre_self__tlb_mapping_1g___4__dom___leneq); }
    if g__pre_self__tlb_mapping_1g___4__dom___lenrng { assume((pre_self_.tlb_mapping_1g)@[4].dom().len() >= k__pre_self__tlb_mapping_1g___4__dom___lenrng_lo && (pre_self_.tlb_mapping_1g)@[4].dom().len() <= k__pre_self__tlb_mapping_1g___4__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_1g___4__dom___contains { assume((pre_self_.tlb_mapping_1g)@[4].dom().contains(k__pre_self__tlb_mapping_1g___4__dom___contains)); }
    if g__pre_self__tlb_mapping_1g___5__dom___empty { assume((pre_self_.tlb_mapping_1g)@[5].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_1g___5__dom___lengt { assume((pre_self_.tlb_mapping_1g)@[5].dom().len() > 0); }
    if g__pre_self__tlb_mapping_1g___5__dom___leneq { assume((pre_self_.tlb_mapping_1g)@[5].dom().len() == k__pre_self__tlb_mapping_1g___5__dom___leneq); }
    if g__pre_self__tlb_mapping_1g___5__dom___lenrng { assume((pre_self_.tlb_mapping_1g)@[5].dom().len() >= k__pre_self__tlb_mapping_1g___5__dom___lenrng_lo && (pre_self_.tlb_mapping_1g)@[5].dom().len() <= k__pre_self__tlb_mapping_1g___5__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_1g___5__dom___contains { assume((pre_self_.tlb_mapping_1g)@[5].dom().contains(k__pre_self__tlb_mapping_1g___5__dom___contains)); }
    if g__pre_self__tlb_mapping_1g___6__dom___empty { assume((pre_self_.tlb_mapping_1g)@[6].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_1g___6__dom___lengt { assume((pre_self_.tlb_mapping_1g)@[6].dom().len() > 0); }
    if g__pre_self__tlb_mapping_1g___6__dom___leneq { assume((pre_self_.tlb_mapping_1g)@[6].dom().len() == k__pre_self__tlb_mapping_1g___6__dom___leneq); }
    if g__pre_self__tlb_mapping_1g___6__dom___lenrng { assume((pre_self_.tlb_mapping_1g)@[6].dom().len() >= k__pre_self__tlb_mapping_1g___6__dom___lenrng_lo && (pre_self_.tlb_mapping_1g)@[6].dom().len() <= k__pre_self__tlb_mapping_1g___6__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_1g___6__dom___contains { assume((pre_self_.tlb_mapping_1g)@[6].dom().contains(k__pre_self__tlb_mapping_1g___6__dom___contains)); }
    if g__pre_self__tlb_mapping_1g___7__dom___empty { assume((pre_self_.tlb_mapping_1g)@[7].dom() == Set::<VAddr>::empty()); }
    if g__pre_self__tlb_mapping_1g___7__dom___lengt { assume((pre_self_.tlb_mapping_1g)@[7].dom().len() > 0); }
    if g__pre_self__tlb_mapping_1g___7__dom___leneq { assume((pre_self_.tlb_mapping_1g)@[7].dom().len() == k__pre_self__tlb_mapping_1g___7__dom___leneq); }
    if g__pre_self__tlb_mapping_1g___7__dom___lenrng { assume((pre_self_.tlb_mapping_1g)@[7].dom().len() >= k__pre_self__tlb_mapping_1g___7__dom___lenrng_lo && (pre_self_.tlb_mapping_1g)@[7].dom().len() <= k__pre_self__tlb_mapping_1g___7__dom___lenrng_hi); }
    if g__pre_self__tlb_mapping_1g___7__dom___contains { assume((pre_self_.tlb_mapping_1g)@[7].dom().contains(k__pre_self__tlb_mapping_1g___7__dom___contains)); }
    if g_target_entry_write_is_true { assume(target_entry.write == true); }
    if g_target_entry_write_is_false { assume(target_entry.write == false); }
    if g_target_entry_execute_disable_is_true { assume(target_entry.execute_disable == true); }
    if g_target_entry_execute_disable_is_false { assume(target_entry.execute_disable == false); }
    if g_post1_self__pcid_is_Some { assume(post1_self_.pcid is Some); }
    if g_post1_self__pcid_is_None { assume(post1_self_.pcid is None); }
    if g_post1_self__ioid_is_Some { assume(post1_self_.ioid is Some); }
    if g_post1_self__ioid_is_None { assume(post1_self_.ioid is None); }
    if g_post1_self__kernel_l4_end_eq { assume(post1_self_.kernel_l4_end as int == k_post1_self__kernel_l4_end_eq); }
    if g_post1_self__kernel_l4_end_rng { assume(post1_self_.kernel_l4_end as int >= k_post1_self__kernel_l4_end_rng_lo && post1_self_.kernel_l4_end as int <= k_post1_self__kernel_l4_end_rng_hi); }
    if g__post1_self__l4_table___dom___empty { assume((post1_self_.l4_table)@.dom() == Set::<PageMapPtr>::empty()); }
    if g__post1_self__l4_table___dom___lengt { assume((post1_self_.l4_table)@.dom().len() > 0); }
    if g__post1_self__l4_table___dom___leneq { assume((post1_self_.l4_table)@.dom().len() == k__post1_self__l4_table___dom___leneq); }
    if g__post1_self__l4_table___dom___lenrng { assume((post1_self_.l4_table)@.dom().len() >= k__post1_self__l4_table___dom___lenrng_lo && (post1_self_.l4_table)@.dom().len() <= k__post1_self__l4_table___dom___lenrng_hi); }
    if g__post1_self__l4_table___dom___contains { assume((post1_self_.l4_table)@.dom().contains(k__post1_self__l4_table___dom___contains)); }
    if g__post1_self__l3_rev_map___dom___empty { assume((post1_self_.l3_rev_map)@.dom() == Set::<PageMapPtr>::empty()); }
    if g__post1_self__l3_rev_map___dom___lengt { assume((post1_self_.l3_rev_map)@.dom().len() > 0); }
    if g__post1_self__l3_rev_map___dom___leneq { assume((post1_self_.l3_rev_map)@.dom().len() == k__post1_self__l3_rev_map___dom___leneq); }
    if g__post1_self__l3_rev_map___dom___lenrng { assume((post1_self_.l3_rev_map)@.dom().len() >= k__post1_self__l3_rev_map___dom___lenrng_lo && (post1_self_.l3_rev_map)@.dom().len() <= k__post1_self__l3_rev_map___dom___lenrng_hi); }
    if g__post1_self__l3_rev_map___dom___contains { assume((post1_self_.l3_rev_map)@.dom().contains(k__post1_self__l3_rev_map___dom___contains)); }
    if g__post1_self__l3_tables___dom___empty { assume((post1_self_.l3_tables)@.dom() == Set::<PageMapPtr>::empty()); }
    if g__post1_self__l3_tables___dom___lengt { assume((post1_self_.l3_tables)@.dom().len() > 0); }
    if g__post1_self__l3_tables___dom___leneq { assume((post1_self_.l3_tables)@.dom().len() == k__post1_self__l3_tables___dom___leneq); }
    if g__post1_self__l3_tables___dom___lenrng { assume((post1_self_.l3_tables)@.dom().len() >= k__post1_self__l3_tables___dom___lenrng_lo && (post1_self_.l3_tables)@.dom().len() <= k__post1_self__l3_tables___dom___lenrng_hi); }
    if g__post1_self__l3_tables___dom___contains { assume((post1_self_.l3_tables)@.dom().contains(k__post1_self__l3_tables___dom___contains)); }
    if g__post1_self__l2_rev_map___dom___empty { assume((post1_self_.l2_rev_map)@.dom() == Set::<PageMapPtr>::empty()); }
    if g__post1_self__l2_rev_map___dom___lengt { assume((post1_self_.l2_rev_map)@.dom().len() > 0); }
    if g__post1_self__l2_rev_map___dom___leneq { assume((post1_self_.l2_rev_map)@.dom().len() == k__post1_self__l2_rev_map___dom___leneq); }
    if g__post1_self__l2_rev_map___dom___lenrng { assume((post1_self_.l2_rev_map)@.dom().len() >= k__post1_self__l2_rev_map___dom___lenrng_lo && (post1_self_.l2_rev_map)@.dom().len() <= k__post1_self__l2_rev_map___dom___lenrng_hi); }
    if g__post1_self__l2_rev_map___dom___contains { assume((post1_self_.l2_rev_map)@.dom().contains(k__post1_self__l2_rev_map___dom___contains)); }
    if g__post1_self__l2_tables___dom___empty { assume((post1_self_.l2_tables)@.dom() == Set::<PageMapPtr>::empty()); }
    if g__post1_self__l2_tables___dom___lengt { assume((post1_self_.l2_tables)@.dom().len() > 0); }
    if g__post1_self__l2_tables___dom___leneq { assume((post1_self_.l2_tables)@.dom().len() == k__post1_self__l2_tables___dom___leneq); }
    if g__post1_self__l2_tables___dom___lenrng { assume((post1_self_.l2_tables)@.dom().len() >= k__post1_self__l2_tables___dom___lenrng_lo && (post1_self_.l2_tables)@.dom().len() <= k__post1_self__l2_tables___dom___lenrng_hi); }
    if g__post1_self__l2_tables___dom___contains { assume((post1_self_.l2_tables)@.dom().contains(k__post1_self__l2_tables___dom___contains)); }
    if g__post1_self__l1_rev_map___dom___empty { assume((post1_self_.l1_rev_map)@.dom() == Set::<PageMapPtr>::empty()); }
    if g__post1_self__l1_rev_map___dom___lengt { assume((post1_self_.l1_rev_map)@.dom().len() > 0); }
    if g__post1_self__l1_rev_map___dom___leneq { assume((post1_self_.l1_rev_map)@.dom().len() == k__post1_self__l1_rev_map___dom___leneq); }
    if g__post1_self__l1_rev_map___dom___lenrng { assume((post1_self_.l1_rev_map)@.dom().len() >= k__post1_self__l1_rev_map___dom___lenrng_lo && (post1_self_.l1_rev_map)@.dom().len() <= k__post1_self__l1_rev_map___dom___lenrng_hi); }
    if g__post1_self__l1_rev_map___dom___contains { assume((post1_self_.l1_rev_map)@.dom().contains(k__post1_self__l1_rev_map___dom___contains)); }
    if g__post1_self__l1_tables___dom___empty { assume((post1_self_.l1_tables)@.dom() == Set::<PageMapPtr>::empty()); }
    if g__post1_self__l1_tables___dom___lengt { assume((post1_self_.l1_tables)@.dom().len() > 0); }
    if g__post1_self__l1_tables___dom___leneq { assume((post1_self_.l1_tables)@.dom().len() == k__post1_self__l1_tables___dom___leneq); }
    if g__post1_self__l1_tables___dom___lenrng { assume((post1_self_.l1_tables)@.dom().len() >= k__post1_self__l1_tables___dom___lenrng_lo && (post1_self_.l1_tables)@.dom().len() <= k__post1_self__l1_tables___dom___lenrng_hi); }
    if g__post1_self__l1_tables___dom___contains { assume((post1_self_.l1_tables)@.dom().contains(k__post1_self__l1_tables___dom___contains)); }
    if g__post1_self__mapping_4k___dom___empty { assume((post1_self_.mapping_4k)@.dom() == Set::<VAddr>::empty()); }
    if g__post1_self__mapping_4k___dom___lengt { assume((post1_self_.mapping_4k)@.dom().len() > 0); }
    if g__post1_self__mapping_4k___dom___leneq { assume((post1_self_.mapping_4k)@.dom().len() == k__post1_self__mapping_4k___dom___leneq); }
    if g__post1_self__mapping_4k___dom___lenrng { assume((post1_self_.mapping_4k)@.dom().len() >= k__post1_self__mapping_4k___dom___lenrng_lo && (post1_self_.mapping_4k)@.dom().len() <= k__post1_self__mapping_4k___dom___lenrng_hi); }
    if g__post1_self__mapping_4k___dom___contains { assume((post1_self_.mapping_4k)@.dom().contains(k__post1_self__mapping_4k___dom___contains)); }
    if g__post1_self__mapping_2m___dom___empty { assume((post1_self_.mapping_2m)@.dom() == Set::<VAddr>::empty()); }
    if g__post1_self__mapping_2m___dom___lengt { assume((post1_self_.mapping_2m)@.dom().len() > 0); }
    if g__post1_self__mapping_2m___dom___leneq { assume((post1_self_.mapping_2m)@.dom().len() == k__post1_self__mapping_2m___dom___leneq); }
    if g__post1_self__mapping_2m___dom___lenrng { assume((post1_self_.mapping_2m)@.dom().len() >= k__post1_self__mapping_2m___dom___lenrng_lo && (post1_self_.mapping_2m)@.dom().len() <= k__post1_self__mapping_2m___dom___lenrng_hi); }
    if g__post1_self__mapping_2m___dom___contains { assume((post1_self_.mapping_2m)@.dom().contains(k__post1_self__mapping_2m___dom___contains)); }
    if g__post1_self__mapping_1g___dom___empty { assume((post1_self_.mapping_1g)@.dom() == Set::<VAddr>::empty()); }
    if g__post1_self__mapping_1g___dom___lengt { assume((post1_self_.mapping_1g)@.dom().len() > 0); }
    if g__post1_self__mapping_1g___dom___leneq { assume((post1_self_.mapping_1g)@.dom().len() == k__post1_self__mapping_1g___dom___leneq); }
    if g__post1_self__mapping_1g___dom___lenrng { assume((post1_self_.mapping_1g)@.dom().len() >= k__post1_self__mapping_1g___dom___lenrng_lo && (post1_self_.mapping_1g)@.dom().len() <= k__post1_self__mapping_1g___dom___lenrng_hi); }
    if g__post1_self__mapping_1g___dom___contains { assume((post1_self_.mapping_1g)@.dom().contains(k__post1_self__mapping_1g___dom___contains)); }
    if g__post1_self__kernel_entries___leneq { assume((post1_self_.kernel_entries)@.len() == k__post1_self__kernel_entries___leneq); }
    if g__post1_self__kernel_entries___lenrng { assume((post1_self_.kernel_entries)@.len() >= k__post1_self__kernel_entries___lenrng_lo && (post1_self_.kernel_entries)@.len() <= k__post1_self__kernel_entries___lenrng_hi); }
    if g__post1_self__kernel_entries___0__perm_present_is_true { assume((post1_self_.kernel_entries)@[0].perm.present == true); }
    if g__post1_self__kernel_entries___0__perm_present_is_false { assume((post1_self_.kernel_entries)@[0].perm.present == false); }
    if g__post1_self__kernel_entries___0__perm_ps_is_true { assume((post1_self_.kernel_entries)@[0].perm.ps == true); }
    if g__post1_self__kernel_entries___0__perm_ps_is_false { assume((post1_self_.kernel_entries)@[0].perm.ps == false); }
    if g__post1_self__kernel_entries___0__perm_write_is_true { assume((post1_self_.kernel_entries)@[0].perm.write == true); }
    if g__post1_self__kernel_entries___0__perm_write_is_false { assume((post1_self_.kernel_entries)@[0].perm.write == false); }
    if g__post1_self__kernel_entries___0__perm_execute_disable_is_true { assume((post1_self_.kernel_entries)@[0].perm.execute_disable == true); }
    if g__post1_self__kernel_entries___0__perm_execute_disable_is_false { assume((post1_self_.kernel_entries)@[0].perm.execute_disable == false); }
    if g__post1_self__kernel_entries___0__perm_user_is_true { assume((post1_self_.kernel_entries)@[0].perm.user == true); }
    if g__post1_self__kernel_entries___0__perm_user_is_false { assume((post1_self_.kernel_entries)@[0].perm.user == false); }
    if g__post1_self__kernel_entries___1__perm_present_is_true { assume((post1_self_.kernel_entries)@[1].perm.present == true); }
    if g__post1_self__kernel_entries___1__perm_present_is_false { assume((post1_self_.kernel_entries)@[1].perm.present == false); }
    if g__post1_self__kernel_entries___1__perm_ps_is_true { assume((post1_self_.kernel_entries)@[1].perm.ps == true); }
    if g__post1_self__kernel_entries___1__perm_ps_is_false { assume((post1_self_.kernel_entries)@[1].perm.ps == false); }
    if g__post1_self__kernel_entries___1__perm_write_is_true { assume((post1_self_.kernel_entries)@[1].perm.write == true); }
    if g__post1_self__kernel_entries___1__perm_write_is_false { assume((post1_self_.kernel_entries)@[1].perm.write == false); }
    if g__post1_self__kernel_entries___1__perm_execute_disable_is_true { assume((post1_self_.kernel_entries)@[1].perm.execute_disable == true); }
    if g__post1_self__kernel_entries___1__perm_execute_disable_is_false { assume((post1_self_.kernel_entries)@[1].perm.execute_disable == false); }
    if g__post1_self__kernel_entries___1__perm_user_is_true { assume((post1_self_.kernel_entries)@[1].perm.user == true); }
    if g__post1_self__kernel_entries___1__perm_user_is_false { assume((post1_self_.kernel_entries)@[1].perm.user == false); }
    if g__post1_self__kernel_entries___2__perm_present_is_true { assume((post1_self_.kernel_entries)@[2].perm.present == true); }
    if g__post1_self__kernel_entries___2__perm_present_is_false { assume((post1_self_.kernel_entries)@[2].perm.present == false); }
    if g__post1_self__kernel_entries___2__perm_ps_is_true { assume((post1_self_.kernel_entries)@[2].perm.ps == true); }
    if g__post1_self__kernel_entries___2__perm_ps_is_false { assume((post1_self_.kernel_entries)@[2].perm.ps == false); }
    if g__post1_self__kernel_entries___2__perm_write_is_true { assume((post1_self_.kernel_entries)@[2].perm.write == true); }
    if g__post1_self__kernel_entries___2__perm_write_is_false { assume((post1_self_.kernel_entries)@[2].perm.write == false); }
    if g__post1_self__kernel_entries___2__perm_execute_disable_is_true { assume((post1_self_.kernel_entries)@[2].perm.execute_disable == true); }
    if g__post1_self__kernel_entries___2__perm_execute_disable_is_false { assume((post1_self_.kernel_entries)@[2].perm.execute_disable == false); }
    if g__post1_self__kernel_entries___2__perm_user_is_true { assume((post1_self_.kernel_entries)@[2].perm.user == true); }
    if g__post1_self__kernel_entries___2__perm_user_is_false { assume((post1_self_.kernel_entries)@[2].perm.user == false); }
    if g__post1_self__kernel_entries___3__perm_present_is_true { assume((post1_self_.kernel_entries)@[3].perm.present == true); }
    if g__post1_self__kernel_entries___3__perm_present_is_false { assume((post1_self_.kernel_entries)@[3].perm.present == false); }
    if g__post1_self__kernel_entries___3__perm_ps_is_true { assume((post1_self_.kernel_entries)@[3].perm.ps == true); }
    if g__post1_self__kernel_entries___3__perm_ps_is_false { assume((post1_self_.kernel_entries)@[3].perm.ps == false); }
    if g__post1_self__kernel_entries___3__perm_write_is_true { assume((post1_self_.kernel_entries)@[3].perm.write == true); }
    if g__post1_self__kernel_entries___3__perm_write_is_false { assume((post1_self_.kernel_entries)@[3].perm.write == false); }
    if g__post1_self__kernel_entries___3__perm_execute_disable_is_true { assume((post1_self_.kernel_entries)@[3].perm.execute_disable == true); }
    if g__post1_self__kernel_entries___3__perm_execute_disable_is_false { assume((post1_self_.kernel_entries)@[3].perm.execute_disable == false); }
    if g__post1_self__kernel_entries___3__perm_user_is_true { assume((post1_self_.kernel_entries)@[3].perm.user == true); }
    if g__post1_self__kernel_entries___3__perm_user_is_false { assume((post1_self_.kernel_entries)@[3].perm.user == false); }
    if g__post1_self__kernel_entries___4__perm_present_is_true { assume((post1_self_.kernel_entries)@[4].perm.present == true); }
    if g__post1_self__kernel_entries___4__perm_present_is_false { assume((post1_self_.kernel_entries)@[4].perm.present == false); }
    if g__post1_self__kernel_entries___4__perm_ps_is_true { assume((post1_self_.kernel_entries)@[4].perm.ps == true); }
    if g__post1_self__kernel_entries___4__perm_ps_is_false { assume((post1_self_.kernel_entries)@[4].perm.ps == false); }
    if g__post1_self__kernel_entries___4__perm_write_is_true { assume((post1_self_.kernel_entries)@[4].perm.write == true); }
    if g__post1_self__kernel_entries___4__perm_write_is_false { assume((post1_self_.kernel_entries)@[4].perm.write == false); }
    if g__post1_self__kernel_entries___4__perm_execute_disable_is_true { assume((post1_self_.kernel_entries)@[4].perm.execute_disable == true); }
    if g__post1_self__kernel_entries___4__perm_execute_disable_is_false { assume((post1_self_.kernel_entries)@[4].perm.execute_disable == false); }
    if g__post1_self__kernel_entries___4__perm_user_is_true { assume((post1_self_.kernel_entries)@[4].perm.user == true); }
    if g__post1_self__kernel_entries___4__perm_user_is_false { assume((post1_self_.kernel_entries)@[4].perm.user == false); }
    if g__post1_self__kernel_entries___5__perm_present_is_true { assume((post1_self_.kernel_entries)@[5].perm.present == true); }
    if g__post1_self__kernel_entries___5__perm_present_is_false { assume((post1_self_.kernel_entries)@[5].perm.present == false); }
    if g__post1_self__kernel_entries___5__perm_ps_is_true { assume((post1_self_.kernel_entries)@[5].perm.ps == true); }
    if g__post1_self__kernel_entries___5__perm_ps_is_false { assume((post1_self_.kernel_entries)@[5].perm.ps == false); }
    if g__post1_self__kernel_entries___5__perm_write_is_true { assume((post1_self_.kernel_entries)@[5].perm.write == true); }
    if g__post1_self__kernel_entries___5__perm_write_is_false { assume((post1_self_.kernel_entries)@[5].perm.write == false); }
    if g__post1_self__kernel_entries___5__perm_execute_disable_is_true { assume((post1_self_.kernel_entries)@[5].perm.execute_disable == true); }
    if g__post1_self__kernel_entries___5__perm_execute_disable_is_false { assume((post1_self_.kernel_entries)@[5].perm.execute_disable == false); }
    if g__post1_self__kernel_entries___5__perm_user_is_true { assume((post1_self_.kernel_entries)@[5].perm.user == true); }
    if g__post1_self__kernel_entries___5__perm_user_is_false { assume((post1_self_.kernel_entries)@[5].perm.user == false); }
    if g__post1_self__kernel_entries___6__perm_present_is_true { assume((post1_self_.kernel_entries)@[6].perm.present == true); }
    if g__post1_self__kernel_entries___6__perm_present_is_false { assume((post1_self_.kernel_entries)@[6].perm.present == false); }
    if g__post1_self__kernel_entries___6__perm_ps_is_true { assume((post1_self_.kernel_entries)@[6].perm.ps == true); }
    if g__post1_self__kernel_entries___6__perm_ps_is_false { assume((post1_self_.kernel_entries)@[6].perm.ps == false); }
    if g__post1_self__kernel_entries___6__perm_write_is_true { assume((post1_self_.kernel_entries)@[6].perm.write == true); }
    if g__post1_self__kernel_entries___6__perm_write_is_false { assume((post1_self_.kernel_entries)@[6].perm.write == false); }
    if g__post1_self__kernel_entries___6__perm_execute_disable_is_true { assume((post1_self_.kernel_entries)@[6].perm.execute_disable == true); }
    if g__post1_self__kernel_entries___6__perm_execute_disable_is_false { assume((post1_self_.kernel_entries)@[6].perm.execute_disable == false); }
    if g__post1_self__kernel_entries___6__perm_user_is_true { assume((post1_self_.kernel_entries)@[6].perm.user == true); }
    if g__post1_self__kernel_entries___6__perm_user_is_false { assume((post1_self_.kernel_entries)@[6].perm.user == false); }
    if g__post1_self__kernel_entries___7__perm_present_is_true { assume((post1_self_.kernel_entries)@[7].perm.present == true); }
    if g__post1_self__kernel_entries___7__perm_present_is_false { assume((post1_self_.kernel_entries)@[7].perm.present == false); }
    if g__post1_self__kernel_entries___7__perm_ps_is_true { assume((post1_self_.kernel_entries)@[7].perm.ps == true); }
    if g__post1_self__kernel_entries___7__perm_ps_is_false { assume((post1_self_.kernel_entries)@[7].perm.ps == false); }
    if g__post1_self__kernel_entries___7__perm_write_is_true { assume((post1_self_.kernel_entries)@[7].perm.write == true); }
    if g__post1_self__kernel_entries___7__perm_write_is_false { assume((post1_self_.kernel_entries)@[7].perm.write == false); }
    if g__post1_self__kernel_entries___7__perm_execute_disable_is_true { assume((post1_self_.kernel_entries)@[7].perm.execute_disable == true); }
    if g__post1_self__kernel_entries___7__perm_execute_disable_is_false { assume((post1_self_.kernel_entries)@[7].perm.execute_disable == false); }
    if g__post1_self__kernel_entries___7__perm_user_is_true { assume((post1_self_.kernel_entries)@[7].perm.user == true); }
    if g__post1_self__kernel_entries___7__perm_user_is_false { assume((post1_self_.kernel_entries)@[7].perm.user == false); }
    if g__post1_self__tlb_mapping_4k___leneq { assume((post1_self_.tlb_mapping_4k)@.len() == k__post1_self__tlb_mapping_4k___leneq); }
    if g__post1_self__tlb_mapping_4k___lenrng { assume((post1_self_.tlb_mapping_4k)@.len() >= k__post1_self__tlb_mapping_4k___lenrng_lo && (post1_self_.tlb_mapping_4k)@.len() <= k__post1_self__tlb_mapping_4k___lenrng_hi); }
    if g__post1_self__tlb_mapping_4k___0__dom___empty { assume((post1_self_.tlb_mapping_4k)@[0].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_4k___0__dom___lengt { assume((post1_self_.tlb_mapping_4k)@[0].dom().len() > 0); }
    if g__post1_self__tlb_mapping_4k___0__dom___leneq { assume((post1_self_.tlb_mapping_4k)@[0].dom().len() == k__post1_self__tlb_mapping_4k___0__dom___leneq); }
    if g__post1_self__tlb_mapping_4k___0__dom___lenrng { assume((post1_self_.tlb_mapping_4k)@[0].dom().len() >= k__post1_self__tlb_mapping_4k___0__dom___lenrng_lo && (post1_self_.tlb_mapping_4k)@[0].dom().len() <= k__post1_self__tlb_mapping_4k___0__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_4k___0__dom___contains { assume((post1_self_.tlb_mapping_4k)@[0].dom().contains(k__post1_self__tlb_mapping_4k___0__dom___contains)); }
    if g__post1_self__tlb_mapping_4k___1__dom___empty { assume((post1_self_.tlb_mapping_4k)@[1].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_4k___1__dom___lengt { assume((post1_self_.tlb_mapping_4k)@[1].dom().len() > 0); }
    if g__post1_self__tlb_mapping_4k___1__dom___leneq { assume((post1_self_.tlb_mapping_4k)@[1].dom().len() == k__post1_self__tlb_mapping_4k___1__dom___leneq); }
    if g__post1_self__tlb_mapping_4k___1__dom___lenrng { assume((post1_self_.tlb_mapping_4k)@[1].dom().len() >= k__post1_self__tlb_mapping_4k___1__dom___lenrng_lo && (post1_self_.tlb_mapping_4k)@[1].dom().len() <= k__post1_self__tlb_mapping_4k___1__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_4k___1__dom___contains { assume((post1_self_.tlb_mapping_4k)@[1].dom().contains(k__post1_self__tlb_mapping_4k___1__dom___contains)); }
    if g__post1_self__tlb_mapping_4k___2__dom___empty { assume((post1_self_.tlb_mapping_4k)@[2].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_4k___2__dom___lengt { assume((post1_self_.tlb_mapping_4k)@[2].dom().len() > 0); }
    if g__post1_self__tlb_mapping_4k___2__dom___leneq { assume((post1_self_.tlb_mapping_4k)@[2].dom().len() == k__post1_self__tlb_mapping_4k___2__dom___leneq); }
    if g__post1_self__tlb_mapping_4k___2__dom___lenrng { assume((post1_self_.tlb_mapping_4k)@[2].dom().len() >= k__post1_self__tlb_mapping_4k___2__dom___lenrng_lo && (post1_self_.tlb_mapping_4k)@[2].dom().len() <= k__post1_self__tlb_mapping_4k___2__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_4k___2__dom___contains { assume((post1_self_.tlb_mapping_4k)@[2].dom().contains(k__post1_self__tlb_mapping_4k___2__dom___contains)); }
    if g__post1_self__tlb_mapping_4k___3__dom___empty { assume((post1_self_.tlb_mapping_4k)@[3].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_4k___3__dom___lengt { assume((post1_self_.tlb_mapping_4k)@[3].dom().len() > 0); }
    if g__post1_self__tlb_mapping_4k___3__dom___leneq { assume((post1_self_.tlb_mapping_4k)@[3].dom().len() == k__post1_self__tlb_mapping_4k___3__dom___leneq); }
    if g__post1_self__tlb_mapping_4k___3__dom___lenrng { assume((post1_self_.tlb_mapping_4k)@[3].dom().len() >= k__post1_self__tlb_mapping_4k___3__dom___lenrng_lo && (post1_self_.tlb_mapping_4k)@[3].dom().len() <= k__post1_self__tlb_mapping_4k___3__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_4k___3__dom___contains { assume((post1_self_.tlb_mapping_4k)@[3].dom().contains(k__post1_self__tlb_mapping_4k___3__dom___contains)); }
    if g__post1_self__tlb_mapping_4k___4__dom___empty { assume((post1_self_.tlb_mapping_4k)@[4].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_4k___4__dom___lengt { assume((post1_self_.tlb_mapping_4k)@[4].dom().len() > 0); }
    if g__post1_self__tlb_mapping_4k___4__dom___leneq { assume((post1_self_.tlb_mapping_4k)@[4].dom().len() == k__post1_self__tlb_mapping_4k___4__dom___leneq); }
    if g__post1_self__tlb_mapping_4k___4__dom___lenrng { assume((post1_self_.tlb_mapping_4k)@[4].dom().len() >= k__post1_self__tlb_mapping_4k___4__dom___lenrng_lo && (post1_self_.tlb_mapping_4k)@[4].dom().len() <= k__post1_self__tlb_mapping_4k___4__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_4k___4__dom___contains { assume((post1_self_.tlb_mapping_4k)@[4].dom().contains(k__post1_self__tlb_mapping_4k___4__dom___contains)); }
    if g__post1_self__tlb_mapping_4k___5__dom___empty { assume((post1_self_.tlb_mapping_4k)@[5].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_4k___5__dom___lengt { assume((post1_self_.tlb_mapping_4k)@[5].dom().len() > 0); }
    if g__post1_self__tlb_mapping_4k___5__dom___leneq { assume((post1_self_.tlb_mapping_4k)@[5].dom().len() == k__post1_self__tlb_mapping_4k___5__dom___leneq); }
    if g__post1_self__tlb_mapping_4k___5__dom___lenrng { assume((post1_self_.tlb_mapping_4k)@[5].dom().len() >= k__post1_self__tlb_mapping_4k___5__dom___lenrng_lo && (post1_self_.tlb_mapping_4k)@[5].dom().len() <= k__post1_self__tlb_mapping_4k___5__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_4k___5__dom___contains { assume((post1_self_.tlb_mapping_4k)@[5].dom().contains(k__post1_self__tlb_mapping_4k___5__dom___contains)); }
    if g__post1_self__tlb_mapping_4k___6__dom___empty { assume((post1_self_.tlb_mapping_4k)@[6].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_4k___6__dom___lengt { assume((post1_self_.tlb_mapping_4k)@[6].dom().len() > 0); }
    if g__post1_self__tlb_mapping_4k___6__dom___leneq { assume((post1_self_.tlb_mapping_4k)@[6].dom().len() == k__post1_self__tlb_mapping_4k___6__dom___leneq); }
    if g__post1_self__tlb_mapping_4k___6__dom___lenrng { assume((post1_self_.tlb_mapping_4k)@[6].dom().len() >= k__post1_self__tlb_mapping_4k___6__dom___lenrng_lo && (post1_self_.tlb_mapping_4k)@[6].dom().len() <= k__post1_self__tlb_mapping_4k___6__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_4k___6__dom___contains { assume((post1_self_.tlb_mapping_4k)@[6].dom().contains(k__post1_self__tlb_mapping_4k___6__dom___contains)); }
    if g__post1_self__tlb_mapping_4k___7__dom___empty { assume((post1_self_.tlb_mapping_4k)@[7].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_4k___7__dom___lengt { assume((post1_self_.tlb_mapping_4k)@[7].dom().len() > 0); }
    if g__post1_self__tlb_mapping_4k___7__dom___leneq { assume((post1_self_.tlb_mapping_4k)@[7].dom().len() == k__post1_self__tlb_mapping_4k___7__dom___leneq); }
    if g__post1_self__tlb_mapping_4k___7__dom___lenrng { assume((post1_self_.tlb_mapping_4k)@[7].dom().len() >= k__post1_self__tlb_mapping_4k___7__dom___lenrng_lo && (post1_self_.tlb_mapping_4k)@[7].dom().len() <= k__post1_self__tlb_mapping_4k___7__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_4k___7__dom___contains { assume((post1_self_.tlb_mapping_4k)@[7].dom().contains(k__post1_self__tlb_mapping_4k___7__dom___contains)); }
    if g__post1_self__tlb_mapping_2m___leneq { assume((post1_self_.tlb_mapping_2m)@.len() == k__post1_self__tlb_mapping_2m___leneq); }
    if g__post1_self__tlb_mapping_2m___lenrng { assume((post1_self_.tlb_mapping_2m)@.len() >= k__post1_self__tlb_mapping_2m___lenrng_lo && (post1_self_.tlb_mapping_2m)@.len() <= k__post1_self__tlb_mapping_2m___lenrng_hi); }
    if g__post1_self__tlb_mapping_2m___0__dom___empty { assume((post1_self_.tlb_mapping_2m)@[0].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_2m___0__dom___lengt { assume((post1_self_.tlb_mapping_2m)@[0].dom().len() > 0); }
    if g__post1_self__tlb_mapping_2m___0__dom___leneq { assume((post1_self_.tlb_mapping_2m)@[0].dom().len() == k__post1_self__tlb_mapping_2m___0__dom___leneq); }
    if g__post1_self__tlb_mapping_2m___0__dom___lenrng { assume((post1_self_.tlb_mapping_2m)@[0].dom().len() >= k__post1_self__tlb_mapping_2m___0__dom___lenrng_lo && (post1_self_.tlb_mapping_2m)@[0].dom().len() <= k__post1_self__tlb_mapping_2m___0__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_2m___0__dom___contains { assume((post1_self_.tlb_mapping_2m)@[0].dom().contains(k__post1_self__tlb_mapping_2m___0__dom___contains)); }
    if g__post1_self__tlb_mapping_2m___1__dom___empty { assume((post1_self_.tlb_mapping_2m)@[1].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_2m___1__dom___lengt { assume((post1_self_.tlb_mapping_2m)@[1].dom().len() > 0); }
    if g__post1_self__tlb_mapping_2m___1__dom___leneq { assume((post1_self_.tlb_mapping_2m)@[1].dom().len() == k__post1_self__tlb_mapping_2m___1__dom___leneq); }
    if g__post1_self__tlb_mapping_2m___1__dom___lenrng { assume((post1_self_.tlb_mapping_2m)@[1].dom().len() >= k__post1_self__tlb_mapping_2m___1__dom___lenrng_lo && (post1_self_.tlb_mapping_2m)@[1].dom().len() <= k__post1_self__tlb_mapping_2m___1__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_2m___1__dom___contains { assume((post1_self_.tlb_mapping_2m)@[1].dom().contains(k__post1_self__tlb_mapping_2m___1__dom___contains)); }
    if g__post1_self__tlb_mapping_2m___2__dom___empty { assume((post1_self_.tlb_mapping_2m)@[2].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_2m___2__dom___lengt { assume((post1_self_.tlb_mapping_2m)@[2].dom().len() > 0); }
    if g__post1_self__tlb_mapping_2m___2__dom___leneq { assume((post1_self_.tlb_mapping_2m)@[2].dom().len() == k__post1_self__tlb_mapping_2m___2__dom___leneq); }
    if g__post1_self__tlb_mapping_2m___2__dom___lenrng { assume((post1_self_.tlb_mapping_2m)@[2].dom().len() >= k__post1_self__tlb_mapping_2m___2__dom___lenrng_lo && (post1_self_.tlb_mapping_2m)@[2].dom().len() <= k__post1_self__tlb_mapping_2m___2__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_2m___2__dom___contains { assume((post1_self_.tlb_mapping_2m)@[2].dom().contains(k__post1_self__tlb_mapping_2m___2__dom___contains)); }
    if g__post1_self__tlb_mapping_2m___3__dom___empty { assume((post1_self_.tlb_mapping_2m)@[3].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_2m___3__dom___lengt { assume((post1_self_.tlb_mapping_2m)@[3].dom().len() > 0); }
    if g__post1_self__tlb_mapping_2m___3__dom___leneq { assume((post1_self_.tlb_mapping_2m)@[3].dom().len() == k__post1_self__tlb_mapping_2m___3__dom___leneq); }
    if g__post1_self__tlb_mapping_2m___3__dom___lenrng { assume((post1_self_.tlb_mapping_2m)@[3].dom().len() >= k__post1_self__tlb_mapping_2m___3__dom___lenrng_lo && (post1_self_.tlb_mapping_2m)@[3].dom().len() <= k__post1_self__tlb_mapping_2m___3__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_2m___3__dom___contains { assume((post1_self_.tlb_mapping_2m)@[3].dom().contains(k__post1_self__tlb_mapping_2m___3__dom___contains)); }
    if g__post1_self__tlb_mapping_2m___4__dom___empty { assume((post1_self_.tlb_mapping_2m)@[4].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_2m___4__dom___lengt { assume((post1_self_.tlb_mapping_2m)@[4].dom().len() > 0); }
    if g__post1_self__tlb_mapping_2m___4__dom___leneq { assume((post1_self_.tlb_mapping_2m)@[4].dom().len() == k__post1_self__tlb_mapping_2m___4__dom___leneq); }
    if g__post1_self__tlb_mapping_2m___4__dom___lenrng { assume((post1_self_.tlb_mapping_2m)@[4].dom().len() >= k__post1_self__tlb_mapping_2m___4__dom___lenrng_lo && (post1_self_.tlb_mapping_2m)@[4].dom().len() <= k__post1_self__tlb_mapping_2m___4__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_2m___4__dom___contains { assume((post1_self_.tlb_mapping_2m)@[4].dom().contains(k__post1_self__tlb_mapping_2m___4__dom___contains)); }
    if g__post1_self__tlb_mapping_2m___5__dom___empty { assume((post1_self_.tlb_mapping_2m)@[5].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_2m___5__dom___lengt { assume((post1_self_.tlb_mapping_2m)@[5].dom().len() > 0); }
    if g__post1_self__tlb_mapping_2m___5__dom___leneq { assume((post1_self_.tlb_mapping_2m)@[5].dom().len() == k__post1_self__tlb_mapping_2m___5__dom___leneq); }
    if g__post1_self__tlb_mapping_2m___5__dom___lenrng { assume((post1_self_.tlb_mapping_2m)@[5].dom().len() >= k__post1_self__tlb_mapping_2m___5__dom___lenrng_lo && (post1_self_.tlb_mapping_2m)@[5].dom().len() <= k__post1_self__tlb_mapping_2m___5__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_2m___5__dom___contains { assume((post1_self_.tlb_mapping_2m)@[5].dom().contains(k__post1_self__tlb_mapping_2m___5__dom___contains)); }
    if g__post1_self__tlb_mapping_2m___6__dom___empty { assume((post1_self_.tlb_mapping_2m)@[6].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_2m___6__dom___lengt { assume((post1_self_.tlb_mapping_2m)@[6].dom().len() > 0); }
    if g__post1_self__tlb_mapping_2m___6__dom___leneq { assume((post1_self_.tlb_mapping_2m)@[6].dom().len() == k__post1_self__tlb_mapping_2m___6__dom___leneq); }
    if g__post1_self__tlb_mapping_2m___6__dom___lenrng { assume((post1_self_.tlb_mapping_2m)@[6].dom().len() >= k__post1_self__tlb_mapping_2m___6__dom___lenrng_lo && (post1_self_.tlb_mapping_2m)@[6].dom().len() <= k__post1_self__tlb_mapping_2m___6__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_2m___6__dom___contains { assume((post1_self_.tlb_mapping_2m)@[6].dom().contains(k__post1_self__tlb_mapping_2m___6__dom___contains)); }
    if g__post1_self__tlb_mapping_2m___7__dom___empty { assume((post1_self_.tlb_mapping_2m)@[7].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_2m___7__dom___lengt { assume((post1_self_.tlb_mapping_2m)@[7].dom().len() > 0); }
    if g__post1_self__tlb_mapping_2m___7__dom___leneq { assume((post1_self_.tlb_mapping_2m)@[7].dom().len() == k__post1_self__tlb_mapping_2m___7__dom___leneq); }
    if g__post1_self__tlb_mapping_2m___7__dom___lenrng { assume((post1_self_.tlb_mapping_2m)@[7].dom().len() >= k__post1_self__tlb_mapping_2m___7__dom___lenrng_lo && (post1_self_.tlb_mapping_2m)@[7].dom().len() <= k__post1_self__tlb_mapping_2m___7__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_2m___7__dom___contains { assume((post1_self_.tlb_mapping_2m)@[7].dom().contains(k__post1_self__tlb_mapping_2m___7__dom___contains)); }
    if g__post1_self__tlb_mapping_1g___leneq { assume((post1_self_.tlb_mapping_1g)@.len() == k__post1_self__tlb_mapping_1g___leneq); }
    if g__post1_self__tlb_mapping_1g___lenrng { assume((post1_self_.tlb_mapping_1g)@.len() >= k__post1_self__tlb_mapping_1g___lenrng_lo && (post1_self_.tlb_mapping_1g)@.len() <= k__post1_self__tlb_mapping_1g___lenrng_hi); }
    if g__post1_self__tlb_mapping_1g___0__dom___empty { assume((post1_self_.tlb_mapping_1g)@[0].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_1g___0__dom___lengt { assume((post1_self_.tlb_mapping_1g)@[0].dom().len() > 0); }
    if g__post1_self__tlb_mapping_1g___0__dom___leneq { assume((post1_self_.tlb_mapping_1g)@[0].dom().len() == k__post1_self__tlb_mapping_1g___0__dom___leneq); }
    if g__post1_self__tlb_mapping_1g___0__dom___lenrng { assume((post1_self_.tlb_mapping_1g)@[0].dom().len() >= k__post1_self__tlb_mapping_1g___0__dom___lenrng_lo && (post1_self_.tlb_mapping_1g)@[0].dom().len() <= k__post1_self__tlb_mapping_1g___0__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_1g___0__dom___contains { assume((post1_self_.tlb_mapping_1g)@[0].dom().contains(k__post1_self__tlb_mapping_1g___0__dom___contains)); }
    if g__post1_self__tlb_mapping_1g___1__dom___empty { assume((post1_self_.tlb_mapping_1g)@[1].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_1g___1__dom___lengt { assume((post1_self_.tlb_mapping_1g)@[1].dom().len() > 0); }
    if g__post1_self__tlb_mapping_1g___1__dom___leneq { assume((post1_self_.tlb_mapping_1g)@[1].dom().len() == k__post1_self__tlb_mapping_1g___1__dom___leneq); }
    if g__post1_self__tlb_mapping_1g___1__dom___lenrng { assume((post1_self_.tlb_mapping_1g)@[1].dom().len() >= k__post1_self__tlb_mapping_1g___1__dom___lenrng_lo && (post1_self_.tlb_mapping_1g)@[1].dom().len() <= k__post1_self__tlb_mapping_1g___1__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_1g___1__dom___contains { assume((post1_self_.tlb_mapping_1g)@[1].dom().contains(k__post1_self__tlb_mapping_1g___1__dom___contains)); }
    if g__post1_self__tlb_mapping_1g___2__dom___empty { assume((post1_self_.tlb_mapping_1g)@[2].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_1g___2__dom___lengt { assume((post1_self_.tlb_mapping_1g)@[2].dom().len() > 0); }
    if g__post1_self__tlb_mapping_1g___2__dom___leneq { assume((post1_self_.tlb_mapping_1g)@[2].dom().len() == k__post1_self__tlb_mapping_1g___2__dom___leneq); }
    if g__post1_self__tlb_mapping_1g___2__dom___lenrng { assume((post1_self_.tlb_mapping_1g)@[2].dom().len() >= k__post1_self__tlb_mapping_1g___2__dom___lenrng_lo && (post1_self_.tlb_mapping_1g)@[2].dom().len() <= k__post1_self__tlb_mapping_1g___2__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_1g___2__dom___contains { assume((post1_self_.tlb_mapping_1g)@[2].dom().contains(k__post1_self__tlb_mapping_1g___2__dom___contains)); }
    if g__post1_self__tlb_mapping_1g___3__dom___empty { assume((post1_self_.tlb_mapping_1g)@[3].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_1g___3__dom___lengt { assume((post1_self_.tlb_mapping_1g)@[3].dom().len() > 0); }
    if g__post1_self__tlb_mapping_1g___3__dom___leneq { assume((post1_self_.tlb_mapping_1g)@[3].dom().len() == k__post1_self__tlb_mapping_1g___3__dom___leneq); }
    if g__post1_self__tlb_mapping_1g___3__dom___lenrng { assume((post1_self_.tlb_mapping_1g)@[3].dom().len() >= k__post1_self__tlb_mapping_1g___3__dom___lenrng_lo && (post1_self_.tlb_mapping_1g)@[3].dom().len() <= k__post1_self__tlb_mapping_1g___3__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_1g___3__dom___contains { assume((post1_self_.tlb_mapping_1g)@[3].dom().contains(k__post1_self__tlb_mapping_1g___3__dom___contains)); }
    if g__post1_self__tlb_mapping_1g___4__dom___empty { assume((post1_self_.tlb_mapping_1g)@[4].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_1g___4__dom___lengt { assume((post1_self_.tlb_mapping_1g)@[4].dom().len() > 0); }
    if g__post1_self__tlb_mapping_1g___4__dom___leneq { assume((post1_self_.tlb_mapping_1g)@[4].dom().len() == k__post1_self__tlb_mapping_1g___4__dom___leneq); }
    if g__post1_self__tlb_mapping_1g___4__dom___lenrng { assume((post1_self_.tlb_mapping_1g)@[4].dom().len() >= k__post1_self__tlb_mapping_1g___4__dom___lenrng_lo && (post1_self_.tlb_mapping_1g)@[4].dom().len() <= k__post1_self__tlb_mapping_1g___4__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_1g___4__dom___contains { assume((post1_self_.tlb_mapping_1g)@[4].dom().contains(k__post1_self__tlb_mapping_1g___4__dom___contains)); }
    if g__post1_self__tlb_mapping_1g___5__dom___empty { assume((post1_self_.tlb_mapping_1g)@[5].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_1g___5__dom___lengt { assume((post1_self_.tlb_mapping_1g)@[5].dom().len() > 0); }
    if g__post1_self__tlb_mapping_1g___5__dom___leneq { assume((post1_self_.tlb_mapping_1g)@[5].dom().len() == k__post1_self__tlb_mapping_1g___5__dom___leneq); }
    if g__post1_self__tlb_mapping_1g___5__dom___lenrng { assume((post1_self_.tlb_mapping_1g)@[5].dom().len() >= k__post1_self__tlb_mapping_1g___5__dom___lenrng_lo && (post1_self_.tlb_mapping_1g)@[5].dom().len() <= k__post1_self__tlb_mapping_1g___5__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_1g___5__dom___contains { assume((post1_self_.tlb_mapping_1g)@[5].dom().contains(k__post1_self__tlb_mapping_1g___5__dom___contains)); }
    if g__post1_self__tlb_mapping_1g___6__dom___empty { assume((post1_self_.tlb_mapping_1g)@[6].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_1g___6__dom___lengt { assume((post1_self_.tlb_mapping_1g)@[6].dom().len() > 0); }
    if g__post1_self__tlb_mapping_1g___6__dom___leneq { assume((post1_self_.tlb_mapping_1g)@[6].dom().len() == k__post1_self__tlb_mapping_1g___6__dom___leneq); }
    if g__post1_self__tlb_mapping_1g___6__dom___lenrng { assume((post1_self_.tlb_mapping_1g)@[6].dom().len() >= k__post1_self__tlb_mapping_1g___6__dom___lenrng_lo && (post1_self_.tlb_mapping_1g)@[6].dom().len() <= k__post1_self__tlb_mapping_1g___6__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_1g___6__dom___contains { assume((post1_self_.tlb_mapping_1g)@[6].dom().contains(k__post1_self__tlb_mapping_1g___6__dom___contains)); }
    if g__post1_self__tlb_mapping_1g___7__dom___empty { assume((post1_self_.tlb_mapping_1g)@[7].dom() == Set::<VAddr>::empty()); }
    if g__post1_self__tlb_mapping_1g___7__dom___lengt { assume((post1_self_.tlb_mapping_1g)@[7].dom().len() > 0); }
    if g__post1_self__tlb_mapping_1g___7__dom___leneq { assume((post1_self_.tlb_mapping_1g)@[7].dom().len() == k__post1_self__tlb_mapping_1g___7__dom___leneq); }
    if g__post1_self__tlb_mapping_1g___7__dom___lenrng { assume((post1_self_.tlb_mapping_1g)@[7].dom().len() >= k__post1_self__tlb_mapping_1g___7__dom___lenrng_lo && (post1_self_.tlb_mapping_1g)@[7].dom().len() <= k__post1_self__tlb_mapping_1g___7__dom___lenrng_hi); }
    if g__post1_self__tlb_mapping_1g___7__dom___contains { assume((post1_self_.tlb_mapping_1g)@[7].dom().contains(k__post1_self__tlb_mapping_1g___7__dom___contains)); }
    if g_post2_self__pcid_is_Some { assume(post2_self_.pcid is Some); }
    if g_post2_self__pcid_is_None { assume(post2_self_.pcid is None); }
    if g_post2_self__ioid_is_Some { assume(post2_self_.ioid is Some); }
    if g_post2_self__ioid_is_None { assume(post2_self_.ioid is None); }
    if g_post2_self__kernel_l4_end_eq { assume(post2_self_.kernel_l4_end as int == k_post2_self__kernel_l4_end_eq); }
    if g_post2_self__kernel_l4_end_rng { assume(post2_self_.kernel_l4_end as int >= k_post2_self__kernel_l4_end_rng_lo && post2_self_.kernel_l4_end as int <= k_post2_self__kernel_l4_end_rng_hi); }
    if g__post2_self__l4_table___dom___empty { assume((post2_self_.l4_table)@.dom() == Set::<PageMapPtr>::empty()); }
    if g__post2_self__l4_table___dom___lengt { assume((post2_self_.l4_table)@.dom().len() > 0); }
    if g__post2_self__l4_table___dom___leneq { assume((post2_self_.l4_table)@.dom().len() == k__post2_self__l4_table___dom___leneq); }
    if g__post2_self__l4_table___dom___lenrng { assume((post2_self_.l4_table)@.dom().len() >= k__post2_self__l4_table___dom___lenrng_lo && (post2_self_.l4_table)@.dom().len() <= k__post2_self__l4_table___dom___lenrng_hi); }
    if g__post2_self__l4_table___dom___contains { assume((post2_self_.l4_table)@.dom().contains(k__post2_self__l4_table___dom___contains)); }
    if g__post2_self__l3_rev_map___dom___empty { assume((post2_self_.l3_rev_map)@.dom() == Set::<PageMapPtr>::empty()); }
    if g__post2_self__l3_rev_map___dom___lengt { assume((post2_self_.l3_rev_map)@.dom().len() > 0); }
    if g__post2_self__l3_rev_map___dom___leneq { assume((post2_self_.l3_rev_map)@.dom().len() == k__post2_self__l3_rev_map___dom___leneq); }
    if g__post2_self__l3_rev_map___dom___lenrng { assume((post2_self_.l3_rev_map)@.dom().len() >= k__post2_self__l3_rev_map___dom___lenrng_lo && (post2_self_.l3_rev_map)@.dom().len() <= k__post2_self__l3_rev_map___dom___lenrng_hi); }
    if g__post2_self__l3_rev_map___dom___contains { assume((post2_self_.l3_rev_map)@.dom().contains(k__post2_self__l3_rev_map___dom___contains)); }
    if g__post2_self__l3_tables___dom___empty { assume((post2_self_.l3_tables)@.dom() == Set::<PageMapPtr>::empty()); }
    if g__post2_self__l3_tables___dom___lengt { assume((post2_self_.l3_tables)@.dom().len() > 0); }
    if g__post2_self__l3_tables___dom___leneq { assume((post2_self_.l3_tables)@.dom().len() == k__post2_self__l3_tables___dom___leneq); }
    if g__post2_self__l3_tables___dom___lenrng { assume((post2_self_.l3_tables)@.dom().len() >= k__post2_self__l3_tables___dom___lenrng_lo && (post2_self_.l3_tables)@.dom().len() <= k__post2_self__l3_tables___dom___lenrng_hi); }
    if g__post2_self__l3_tables___dom___contains { assume((post2_self_.l3_tables)@.dom().contains(k__post2_self__l3_tables___dom___contains)); }
    if g__post2_self__l2_rev_map___dom___empty { assume((post2_self_.l2_rev_map)@.dom() == Set::<PageMapPtr>::empty()); }
    if g__post2_self__l2_rev_map___dom___lengt { assume((post2_self_.l2_rev_map)@.dom().len() > 0); }
    if g__post2_self__l2_rev_map___dom___leneq { assume((post2_self_.l2_rev_map)@.dom().len() == k__post2_self__l2_rev_map___dom___leneq); }
    if g__post2_self__l2_rev_map___dom___lenrng { assume((post2_self_.l2_rev_map)@.dom().len() >= k__post2_self__l2_rev_map___dom___lenrng_lo && (post2_self_.l2_rev_map)@.dom().len() <= k__post2_self__l2_rev_map___dom___lenrng_hi); }
    if g__post2_self__l2_rev_map___dom___contains { assume((post2_self_.l2_rev_map)@.dom().contains(k__post2_self__l2_rev_map___dom___contains)); }
    if g__post2_self__l2_tables___dom___empty { assume((post2_self_.l2_tables)@.dom() == Set::<PageMapPtr>::empty()); }
    if g__post2_self__l2_tables___dom___lengt { assume((post2_self_.l2_tables)@.dom().len() > 0); }
    if g__post2_self__l2_tables___dom___leneq { assume((post2_self_.l2_tables)@.dom().len() == k__post2_self__l2_tables___dom___leneq); }
    if g__post2_self__l2_tables___dom___lenrng { assume((post2_self_.l2_tables)@.dom().len() >= k__post2_self__l2_tables___dom___lenrng_lo && (post2_self_.l2_tables)@.dom().len() <= k__post2_self__l2_tables___dom___lenrng_hi); }
    if g__post2_self__l2_tables___dom___contains { assume((post2_self_.l2_tables)@.dom().contains(k__post2_self__l2_tables___dom___contains)); }
    if g__post2_self__l1_rev_map___dom___empty { assume((post2_self_.l1_rev_map)@.dom() == Set::<PageMapPtr>::empty()); }
    if g__post2_self__l1_rev_map___dom___lengt { assume((post2_self_.l1_rev_map)@.dom().len() > 0); }
    if g__post2_self__l1_rev_map___dom___leneq { assume((post2_self_.l1_rev_map)@.dom().len() == k__post2_self__l1_rev_map___dom___leneq); }
    if g__post2_self__l1_rev_map___dom___lenrng { assume((post2_self_.l1_rev_map)@.dom().len() >= k__post2_self__l1_rev_map___dom___lenrng_lo && (post2_self_.l1_rev_map)@.dom().len() <= k__post2_self__l1_rev_map___dom___lenrng_hi); }
    if g__post2_self__l1_rev_map___dom___contains { assume((post2_self_.l1_rev_map)@.dom().contains(k__post2_self__l1_rev_map___dom___contains)); }
    if g__post2_self__l1_tables___dom___empty { assume((post2_self_.l1_tables)@.dom() == Set::<PageMapPtr>::empty()); }
    if g__post2_self__l1_tables___dom___lengt { assume((post2_self_.l1_tables)@.dom().len() > 0); }
    if g__post2_self__l1_tables___dom___leneq { assume((post2_self_.l1_tables)@.dom().len() == k__post2_self__l1_tables___dom___leneq); }
    if g__post2_self__l1_tables___dom___lenrng { assume((post2_self_.l1_tables)@.dom().len() >= k__post2_self__l1_tables___dom___lenrng_lo && (post2_self_.l1_tables)@.dom().len() <= k__post2_self__l1_tables___dom___lenrng_hi); }
    if g__post2_self__l1_tables___dom___contains { assume((post2_self_.l1_tables)@.dom().contains(k__post2_self__l1_tables___dom___contains)); }
    if g__post2_self__mapping_4k___dom___empty { assume((post2_self_.mapping_4k)@.dom() == Set::<VAddr>::empty()); }
    if g__post2_self__mapping_4k___dom___lengt { assume((post2_self_.mapping_4k)@.dom().len() > 0); }
    if g__post2_self__mapping_4k___dom___leneq { assume((post2_self_.mapping_4k)@.dom().len() == k__post2_self__mapping_4k___dom___leneq); }
    if g__post2_self__mapping_4k___dom___lenrng { assume((post2_self_.mapping_4k)@.dom().len() >= k__post2_self__mapping_4k___dom___lenrng_lo && (post2_self_.mapping_4k)@.dom().len() <= k__post2_self__mapping_4k___dom___lenrng_hi); }
    if g__post2_self__mapping_4k___dom___contains { assume((post2_self_.mapping_4k)@.dom().contains(k__post2_self__mapping_4k___dom___contains)); }
    if g__post2_self__mapping_2m___dom___empty { assume((post2_self_.mapping_2m)@.dom() == Set::<VAddr>::empty()); }
    if g__post2_self__mapping_2m___dom___lengt { assume((post2_self_.mapping_2m)@.dom().len() > 0); }
    if g__post2_self__mapping_2m___dom___leneq { assume((post2_self_.mapping_2m)@.dom().len() == k__post2_self__mapping_2m___dom___leneq); }
    if g__post2_self__mapping_2m___dom___lenrng { assume((post2_self_.mapping_2m)@.dom().len() >= k__post2_self__mapping_2m___dom___lenrng_lo && (post2_self_.mapping_2m)@.dom().len() <= k__post2_self__mapping_2m___dom___lenrng_hi); }
    if g__post2_self__mapping_2m___dom___contains { assume((post2_self_.mapping_2m)@.dom().contains(k__post2_self__mapping_2m___dom___contains)); }
    if g__post2_self__mapping_1g___dom___empty { assume((post2_self_.mapping_1g)@.dom() == Set::<VAddr>::empty()); }
    if g__post2_self__mapping_1g___dom___lengt { assume((post2_self_.mapping_1g)@.dom().len() > 0); }
    if g__post2_self__mapping_1g___dom___leneq { assume((post2_self_.mapping_1g)@.dom().len() == k__post2_self__mapping_1g___dom___leneq); }
    if g__post2_self__mapping_1g___dom___lenrng { assume((post2_self_.mapping_1g)@.dom().len() >= k__post2_self__mapping_1g___dom___lenrng_lo && (post2_self_.mapping_1g)@.dom().len() <= k__post2_self__mapping_1g___dom___lenrng_hi); }
    if g__post2_self__mapping_1g___dom___contains { assume((post2_self_.mapping_1g)@.dom().contains(k__post2_self__mapping_1g___dom___contains)); }
    if g__post2_self__kernel_entries___leneq { assume((post2_self_.kernel_entries)@.len() == k__post2_self__kernel_entries___leneq); }
    if g__post2_self__kernel_entries___lenrng { assume((post2_self_.kernel_entries)@.len() >= k__post2_self__kernel_entries___lenrng_lo && (post2_self_.kernel_entries)@.len() <= k__post2_self__kernel_entries___lenrng_hi); }
    if g__post2_self__kernel_entries___0__perm_present_is_true { assume((post2_self_.kernel_entries)@[0].perm.present == true); }
    if g__post2_self__kernel_entries___0__perm_present_is_false { assume((post2_self_.kernel_entries)@[0].perm.present == false); }
    if g__post2_self__kernel_entries___0__perm_ps_is_true { assume((post2_self_.kernel_entries)@[0].perm.ps == true); }
    if g__post2_self__kernel_entries___0__perm_ps_is_false { assume((post2_self_.kernel_entries)@[0].perm.ps == false); }
    if g__post2_self__kernel_entries___0__perm_write_is_true { assume((post2_self_.kernel_entries)@[0].perm.write == true); }
    if g__post2_self__kernel_entries___0__perm_write_is_false { assume((post2_self_.kernel_entries)@[0].perm.write == false); }
    if g__post2_self__kernel_entries___0__perm_execute_disable_is_true { assume((post2_self_.kernel_entries)@[0].perm.execute_disable == true); }
    if g__post2_self__kernel_entries___0__perm_execute_disable_is_false { assume((post2_self_.kernel_entries)@[0].perm.execute_disable == false); }
    if g__post2_self__kernel_entries___0__perm_user_is_true { assume((post2_self_.kernel_entries)@[0].perm.user == true); }
    if g__post2_self__kernel_entries___0__perm_user_is_false { assume((post2_self_.kernel_entries)@[0].perm.user == false); }
    if g__post2_self__kernel_entries___1__perm_present_is_true { assume((post2_self_.kernel_entries)@[1].perm.present == true); }
    if g__post2_self__kernel_entries___1__perm_present_is_false { assume((post2_self_.kernel_entries)@[1].perm.present == false); }
    if g__post2_self__kernel_entries___1__perm_ps_is_true { assume((post2_self_.kernel_entries)@[1].perm.ps == true); }
    if g__post2_self__kernel_entries___1__perm_ps_is_false { assume((post2_self_.kernel_entries)@[1].perm.ps == false); }
    if g__post2_self__kernel_entries___1__perm_write_is_true { assume((post2_self_.kernel_entries)@[1].perm.write == true); }
    if g__post2_self__kernel_entries___1__perm_write_is_false { assume((post2_self_.kernel_entries)@[1].perm.write == false); }
    if g__post2_self__kernel_entries___1__perm_execute_disable_is_true { assume((post2_self_.kernel_entries)@[1].perm.execute_disable == true); }
    if g__post2_self__kernel_entries___1__perm_execute_disable_is_false { assume((post2_self_.kernel_entries)@[1].perm.execute_disable == false); }
    if g__post2_self__kernel_entries___1__perm_user_is_true { assume((post2_self_.kernel_entries)@[1].perm.user == true); }
    if g__post2_self__kernel_entries___1__perm_user_is_false { assume((post2_self_.kernel_entries)@[1].perm.user == false); }
    if g__post2_self__kernel_entries___2__perm_present_is_true { assume((post2_self_.kernel_entries)@[2].perm.present == true); }
    if g__post2_self__kernel_entries___2__perm_present_is_false { assume((post2_self_.kernel_entries)@[2].perm.present == false); }
    if g__post2_self__kernel_entries___2__perm_ps_is_true { assume((post2_self_.kernel_entries)@[2].perm.ps == true); }
    if g__post2_self__kernel_entries___2__perm_ps_is_false { assume((post2_self_.kernel_entries)@[2].perm.ps == false); }
    if g__post2_self__kernel_entries___2__perm_write_is_true { assume((post2_self_.kernel_entries)@[2].perm.write == true); }
    if g__post2_self__kernel_entries___2__perm_write_is_false { assume((post2_self_.kernel_entries)@[2].perm.write == false); }
    if g__post2_self__kernel_entries___2__perm_execute_disable_is_true { assume((post2_self_.kernel_entries)@[2].perm.execute_disable == true); }
    if g__post2_self__kernel_entries___2__perm_execute_disable_is_false { assume((post2_self_.kernel_entries)@[2].perm.execute_disable == false); }
    if g__post2_self__kernel_entries___2__perm_user_is_true { assume((post2_self_.kernel_entries)@[2].perm.user == true); }
    if g__post2_self__kernel_entries___2__perm_user_is_false { assume((post2_self_.kernel_entries)@[2].perm.user == false); }
    if g__post2_self__kernel_entries___3__perm_present_is_true { assume((post2_self_.kernel_entries)@[3].perm.present == true); }
    if g__post2_self__kernel_entries___3__perm_present_is_false { assume((post2_self_.kernel_entries)@[3].perm.present == false); }
    if g__post2_self__kernel_entries___3__perm_ps_is_true { assume((post2_self_.kernel_entries)@[3].perm.ps == true); }
    if g__post2_self__kernel_entries___3__perm_ps_is_false { assume((post2_self_.kernel_entries)@[3].perm.ps == false); }
    if g__post2_self__kernel_entries___3__perm_write_is_true { assume((post2_self_.kernel_entries)@[3].perm.write == true); }
    if g__post2_self__kernel_entries___3__perm_write_is_false { assume((post2_self_.kernel_entries)@[3].perm.write == false); }
    if g__post2_self__kernel_entries___3__perm_execute_disable_is_true { assume((post2_self_.kernel_entries)@[3].perm.execute_disable == true); }
    if g__post2_self__kernel_entries___3__perm_execute_disable_is_false { assume((post2_self_.kernel_entries)@[3].perm.execute_disable == false); }
    if g__post2_self__kernel_entries___3__perm_user_is_true { assume((post2_self_.kernel_entries)@[3].perm.user == true); }
    if g__post2_self__kernel_entries___3__perm_user_is_false { assume((post2_self_.kernel_entries)@[3].perm.user == false); }
    if g__post2_self__kernel_entries___4__perm_present_is_true { assume((post2_self_.kernel_entries)@[4].perm.present == true); }
    if g__post2_self__kernel_entries___4__perm_present_is_false { assume((post2_self_.kernel_entries)@[4].perm.present == false); }
    if g__post2_self__kernel_entries___4__perm_ps_is_true { assume((post2_self_.kernel_entries)@[4].perm.ps == true); }
    if g__post2_self__kernel_entries___4__perm_ps_is_false { assume((post2_self_.kernel_entries)@[4].perm.ps == false); }
    if g__post2_self__kernel_entries___4__perm_write_is_true { assume((post2_self_.kernel_entries)@[4].perm.write == true); }
    if g__post2_self__kernel_entries___4__perm_write_is_false { assume((post2_self_.kernel_entries)@[4].perm.write == false); }
    if g__post2_self__kernel_entries___4__perm_execute_disable_is_true { assume((post2_self_.kernel_entries)@[4].perm.execute_disable == true); }
    if g__post2_self__kernel_entries___4__perm_execute_disable_is_false { assume((post2_self_.kernel_entries)@[4].perm.execute_disable == false); }
    if g__post2_self__kernel_entries___4__perm_user_is_true { assume((post2_self_.kernel_entries)@[4].perm.user == true); }
    if g__post2_self__kernel_entries___4__perm_user_is_false { assume((post2_self_.kernel_entries)@[4].perm.user == false); }
    if g__post2_self__kernel_entries___5__perm_present_is_true { assume((post2_self_.kernel_entries)@[5].perm.present == true); }
    if g__post2_self__kernel_entries___5__perm_present_is_false { assume((post2_self_.kernel_entries)@[5].perm.present == false); }
    if g__post2_self__kernel_entries___5__perm_ps_is_true { assume((post2_self_.kernel_entries)@[5].perm.ps == true); }
    if g__post2_self__kernel_entries___5__perm_ps_is_false { assume((post2_self_.kernel_entries)@[5].perm.ps == false); }
    if g__post2_self__kernel_entries___5__perm_write_is_true { assume((post2_self_.kernel_entries)@[5].perm.write == true); }
    if g__post2_self__kernel_entries___5__perm_write_is_false { assume((post2_self_.kernel_entries)@[5].perm.write == false); }
    if g__post2_self__kernel_entries___5__perm_execute_disable_is_true { assume((post2_self_.kernel_entries)@[5].perm.execute_disable == true); }
    if g__post2_self__kernel_entries___5__perm_execute_disable_is_false { assume((post2_self_.kernel_entries)@[5].perm.execute_disable == false); }
    if g__post2_self__kernel_entries___5__perm_user_is_true { assume((post2_self_.kernel_entries)@[5].perm.user == true); }
    if g__post2_self__kernel_entries___5__perm_user_is_false { assume((post2_self_.kernel_entries)@[5].perm.user == false); }
    if g__post2_self__kernel_entries___6__perm_present_is_true { assume((post2_self_.kernel_entries)@[6].perm.present == true); }
    if g__post2_self__kernel_entries___6__perm_present_is_false { assume((post2_self_.kernel_entries)@[6].perm.present == false); }
    if g__post2_self__kernel_entries___6__perm_ps_is_true { assume((post2_self_.kernel_entries)@[6].perm.ps == true); }
    if g__post2_self__kernel_entries___6__perm_ps_is_false { assume((post2_self_.kernel_entries)@[6].perm.ps == false); }
    if g__post2_self__kernel_entries___6__perm_write_is_true { assume((post2_self_.kernel_entries)@[6].perm.write == true); }
    if g__post2_self__kernel_entries___6__perm_write_is_false { assume((post2_self_.kernel_entries)@[6].perm.write == false); }
    if g__post2_self__kernel_entries___6__perm_execute_disable_is_true { assume((post2_self_.kernel_entries)@[6].perm.execute_disable == true); }
    if g__post2_self__kernel_entries___6__perm_execute_disable_is_false { assume((post2_self_.kernel_entries)@[6].perm.execute_disable == false); }
    if g__post2_self__kernel_entries___6__perm_user_is_true { assume((post2_self_.kernel_entries)@[6].perm.user == true); }
    if g__post2_self__kernel_entries___6__perm_user_is_false { assume((post2_self_.kernel_entries)@[6].perm.user == false); }
    if g__post2_self__kernel_entries___7__perm_present_is_true { assume((post2_self_.kernel_entries)@[7].perm.present == true); }
    if g__post2_self__kernel_entries___7__perm_present_is_false { assume((post2_self_.kernel_entries)@[7].perm.present == false); }
    if g__post2_self__kernel_entries___7__perm_ps_is_true { assume((post2_self_.kernel_entries)@[7].perm.ps == true); }
    if g__post2_self__kernel_entries___7__perm_ps_is_false { assume((post2_self_.kernel_entries)@[7].perm.ps == false); }
    if g__post2_self__kernel_entries___7__perm_write_is_true { assume((post2_self_.kernel_entries)@[7].perm.write == true); }
    if g__post2_self__kernel_entries___7__perm_write_is_false { assume((post2_self_.kernel_entries)@[7].perm.write == false); }
    if g__post2_self__kernel_entries___7__perm_execute_disable_is_true { assume((post2_self_.kernel_entries)@[7].perm.execute_disable == true); }
    if g__post2_self__kernel_entries___7__perm_execute_disable_is_false { assume((post2_self_.kernel_entries)@[7].perm.execute_disable == false); }
    if g__post2_self__kernel_entries___7__perm_user_is_true { assume((post2_self_.kernel_entries)@[7].perm.user == true); }
    if g__post2_self__kernel_entries___7__perm_user_is_false { assume((post2_self_.kernel_entries)@[7].perm.user == false); }
    if g__post2_self__tlb_mapping_4k___leneq { assume((post2_self_.tlb_mapping_4k)@.len() == k__post2_self__tlb_mapping_4k___leneq); }
    if g__post2_self__tlb_mapping_4k___lenrng { assume((post2_self_.tlb_mapping_4k)@.len() >= k__post2_self__tlb_mapping_4k___lenrng_lo && (post2_self_.tlb_mapping_4k)@.len() <= k__post2_self__tlb_mapping_4k___lenrng_hi); }
    if g__post2_self__tlb_mapping_4k___0__dom___empty { assume((post2_self_.tlb_mapping_4k)@[0].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_4k___0__dom___lengt { assume((post2_self_.tlb_mapping_4k)@[0].dom().len() > 0); }
    if g__post2_self__tlb_mapping_4k___0__dom___leneq { assume((post2_self_.tlb_mapping_4k)@[0].dom().len() == k__post2_self__tlb_mapping_4k___0__dom___leneq); }
    if g__post2_self__tlb_mapping_4k___0__dom___lenrng { assume((post2_self_.tlb_mapping_4k)@[0].dom().len() >= k__post2_self__tlb_mapping_4k___0__dom___lenrng_lo && (post2_self_.tlb_mapping_4k)@[0].dom().len() <= k__post2_self__tlb_mapping_4k___0__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_4k___0__dom___contains { assume((post2_self_.tlb_mapping_4k)@[0].dom().contains(k__post2_self__tlb_mapping_4k___0__dom___contains)); }
    if g__post2_self__tlb_mapping_4k___1__dom___empty { assume((post2_self_.tlb_mapping_4k)@[1].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_4k___1__dom___lengt { assume((post2_self_.tlb_mapping_4k)@[1].dom().len() > 0); }
    if g__post2_self__tlb_mapping_4k___1__dom___leneq { assume((post2_self_.tlb_mapping_4k)@[1].dom().len() == k__post2_self__tlb_mapping_4k___1__dom___leneq); }
    if g__post2_self__tlb_mapping_4k___1__dom___lenrng { assume((post2_self_.tlb_mapping_4k)@[1].dom().len() >= k__post2_self__tlb_mapping_4k___1__dom___lenrng_lo && (post2_self_.tlb_mapping_4k)@[1].dom().len() <= k__post2_self__tlb_mapping_4k___1__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_4k___1__dom___contains { assume((post2_self_.tlb_mapping_4k)@[1].dom().contains(k__post2_self__tlb_mapping_4k___1__dom___contains)); }
    if g__post2_self__tlb_mapping_4k___2__dom___empty { assume((post2_self_.tlb_mapping_4k)@[2].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_4k___2__dom___lengt { assume((post2_self_.tlb_mapping_4k)@[2].dom().len() > 0); }
    if g__post2_self__tlb_mapping_4k___2__dom___leneq { assume((post2_self_.tlb_mapping_4k)@[2].dom().len() == k__post2_self__tlb_mapping_4k___2__dom___leneq); }
    if g__post2_self__tlb_mapping_4k___2__dom___lenrng { assume((post2_self_.tlb_mapping_4k)@[2].dom().len() >= k__post2_self__tlb_mapping_4k___2__dom___lenrng_lo && (post2_self_.tlb_mapping_4k)@[2].dom().len() <= k__post2_self__tlb_mapping_4k___2__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_4k___2__dom___contains { assume((post2_self_.tlb_mapping_4k)@[2].dom().contains(k__post2_self__tlb_mapping_4k___2__dom___contains)); }
    if g__post2_self__tlb_mapping_4k___3__dom___empty { assume((post2_self_.tlb_mapping_4k)@[3].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_4k___3__dom___lengt { assume((post2_self_.tlb_mapping_4k)@[3].dom().len() > 0); }
    if g__post2_self__tlb_mapping_4k___3__dom___leneq { assume((post2_self_.tlb_mapping_4k)@[3].dom().len() == k__post2_self__tlb_mapping_4k___3__dom___leneq); }
    if g__post2_self__tlb_mapping_4k___3__dom___lenrng { assume((post2_self_.tlb_mapping_4k)@[3].dom().len() >= k__post2_self__tlb_mapping_4k___3__dom___lenrng_lo && (post2_self_.tlb_mapping_4k)@[3].dom().len() <= k__post2_self__tlb_mapping_4k___3__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_4k___3__dom___contains { assume((post2_self_.tlb_mapping_4k)@[3].dom().contains(k__post2_self__tlb_mapping_4k___3__dom___contains)); }
    if g__post2_self__tlb_mapping_4k___4__dom___empty { assume((post2_self_.tlb_mapping_4k)@[4].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_4k___4__dom___lengt { assume((post2_self_.tlb_mapping_4k)@[4].dom().len() > 0); }
    if g__post2_self__tlb_mapping_4k___4__dom___leneq { assume((post2_self_.tlb_mapping_4k)@[4].dom().len() == k__post2_self__tlb_mapping_4k___4__dom___leneq); }
    if g__post2_self__tlb_mapping_4k___4__dom___lenrng { assume((post2_self_.tlb_mapping_4k)@[4].dom().len() >= k__post2_self__tlb_mapping_4k___4__dom___lenrng_lo && (post2_self_.tlb_mapping_4k)@[4].dom().len() <= k__post2_self__tlb_mapping_4k___4__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_4k___4__dom___contains { assume((post2_self_.tlb_mapping_4k)@[4].dom().contains(k__post2_self__tlb_mapping_4k___4__dom___contains)); }
    if g__post2_self__tlb_mapping_4k___5__dom___empty { assume((post2_self_.tlb_mapping_4k)@[5].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_4k___5__dom___lengt { assume((post2_self_.tlb_mapping_4k)@[5].dom().len() > 0); }
    if g__post2_self__tlb_mapping_4k___5__dom___leneq { assume((post2_self_.tlb_mapping_4k)@[5].dom().len() == k__post2_self__tlb_mapping_4k___5__dom___leneq); }
    if g__post2_self__tlb_mapping_4k___5__dom___lenrng { assume((post2_self_.tlb_mapping_4k)@[5].dom().len() >= k__post2_self__tlb_mapping_4k___5__dom___lenrng_lo && (post2_self_.tlb_mapping_4k)@[5].dom().len() <= k__post2_self__tlb_mapping_4k___5__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_4k___5__dom___contains { assume((post2_self_.tlb_mapping_4k)@[5].dom().contains(k__post2_self__tlb_mapping_4k___5__dom___contains)); }
    if g__post2_self__tlb_mapping_4k___6__dom___empty { assume((post2_self_.tlb_mapping_4k)@[6].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_4k___6__dom___lengt { assume((post2_self_.tlb_mapping_4k)@[6].dom().len() > 0); }
    if g__post2_self__tlb_mapping_4k___6__dom___leneq { assume((post2_self_.tlb_mapping_4k)@[6].dom().len() == k__post2_self__tlb_mapping_4k___6__dom___leneq); }
    if g__post2_self__tlb_mapping_4k___6__dom___lenrng { assume((post2_self_.tlb_mapping_4k)@[6].dom().len() >= k__post2_self__tlb_mapping_4k___6__dom___lenrng_lo && (post2_self_.tlb_mapping_4k)@[6].dom().len() <= k__post2_self__tlb_mapping_4k___6__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_4k___6__dom___contains { assume((post2_self_.tlb_mapping_4k)@[6].dom().contains(k__post2_self__tlb_mapping_4k___6__dom___contains)); }
    if g__post2_self__tlb_mapping_4k___7__dom___empty { assume((post2_self_.tlb_mapping_4k)@[7].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_4k___7__dom___lengt { assume((post2_self_.tlb_mapping_4k)@[7].dom().len() > 0); }
    if g__post2_self__tlb_mapping_4k___7__dom___leneq { assume((post2_self_.tlb_mapping_4k)@[7].dom().len() == k__post2_self__tlb_mapping_4k___7__dom___leneq); }
    if g__post2_self__tlb_mapping_4k___7__dom___lenrng { assume((post2_self_.tlb_mapping_4k)@[7].dom().len() >= k__post2_self__tlb_mapping_4k___7__dom___lenrng_lo && (post2_self_.tlb_mapping_4k)@[7].dom().len() <= k__post2_self__tlb_mapping_4k___7__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_4k___7__dom___contains { assume((post2_self_.tlb_mapping_4k)@[7].dom().contains(k__post2_self__tlb_mapping_4k___7__dom___contains)); }
    if g__post2_self__tlb_mapping_2m___leneq { assume((post2_self_.tlb_mapping_2m)@.len() == k__post2_self__tlb_mapping_2m___leneq); }
    if g__post2_self__tlb_mapping_2m___lenrng { assume((post2_self_.tlb_mapping_2m)@.len() >= k__post2_self__tlb_mapping_2m___lenrng_lo && (post2_self_.tlb_mapping_2m)@.len() <= k__post2_self__tlb_mapping_2m___lenrng_hi); }
    if g__post2_self__tlb_mapping_2m___0__dom___empty { assume((post2_self_.tlb_mapping_2m)@[0].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_2m___0__dom___lengt { assume((post2_self_.tlb_mapping_2m)@[0].dom().len() > 0); }
    if g__post2_self__tlb_mapping_2m___0__dom___leneq { assume((post2_self_.tlb_mapping_2m)@[0].dom().len() == k__post2_self__tlb_mapping_2m___0__dom___leneq); }
    if g__post2_self__tlb_mapping_2m___0__dom___lenrng { assume((post2_self_.tlb_mapping_2m)@[0].dom().len() >= k__post2_self__tlb_mapping_2m___0__dom___lenrng_lo && (post2_self_.tlb_mapping_2m)@[0].dom().len() <= k__post2_self__tlb_mapping_2m___0__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_2m___0__dom___contains { assume((post2_self_.tlb_mapping_2m)@[0].dom().contains(k__post2_self__tlb_mapping_2m___0__dom___contains)); }
    if g__post2_self__tlb_mapping_2m___1__dom___empty { assume((post2_self_.tlb_mapping_2m)@[1].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_2m___1__dom___lengt { assume((post2_self_.tlb_mapping_2m)@[1].dom().len() > 0); }
    if g__post2_self__tlb_mapping_2m___1__dom___leneq { assume((post2_self_.tlb_mapping_2m)@[1].dom().len() == k__post2_self__tlb_mapping_2m___1__dom___leneq); }
    if g__post2_self__tlb_mapping_2m___1__dom___lenrng { assume((post2_self_.tlb_mapping_2m)@[1].dom().len() >= k__post2_self__tlb_mapping_2m___1__dom___lenrng_lo && (post2_self_.tlb_mapping_2m)@[1].dom().len() <= k__post2_self__tlb_mapping_2m___1__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_2m___1__dom___contains { assume((post2_self_.tlb_mapping_2m)@[1].dom().contains(k__post2_self__tlb_mapping_2m___1__dom___contains)); }
    if g__post2_self__tlb_mapping_2m___2__dom___empty { assume((post2_self_.tlb_mapping_2m)@[2].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_2m___2__dom___lengt { assume((post2_self_.tlb_mapping_2m)@[2].dom().len() > 0); }
    if g__post2_self__tlb_mapping_2m___2__dom___leneq { assume((post2_self_.tlb_mapping_2m)@[2].dom().len() == k__post2_self__tlb_mapping_2m___2__dom___leneq); }
    if g__post2_self__tlb_mapping_2m___2__dom___lenrng { assume((post2_self_.tlb_mapping_2m)@[2].dom().len() >= k__post2_self__tlb_mapping_2m___2__dom___lenrng_lo && (post2_self_.tlb_mapping_2m)@[2].dom().len() <= k__post2_self__tlb_mapping_2m___2__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_2m___2__dom___contains { assume((post2_self_.tlb_mapping_2m)@[2].dom().contains(k__post2_self__tlb_mapping_2m___2__dom___contains)); }
    if g__post2_self__tlb_mapping_2m___3__dom___empty { assume((post2_self_.tlb_mapping_2m)@[3].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_2m___3__dom___lengt { assume((post2_self_.tlb_mapping_2m)@[3].dom().len() > 0); }
    if g__post2_self__tlb_mapping_2m___3__dom___leneq { assume((post2_self_.tlb_mapping_2m)@[3].dom().len() == k__post2_self__tlb_mapping_2m___3__dom___leneq); }
    if g__post2_self__tlb_mapping_2m___3__dom___lenrng { assume((post2_self_.tlb_mapping_2m)@[3].dom().len() >= k__post2_self__tlb_mapping_2m___3__dom___lenrng_lo && (post2_self_.tlb_mapping_2m)@[3].dom().len() <= k__post2_self__tlb_mapping_2m___3__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_2m___3__dom___contains { assume((post2_self_.tlb_mapping_2m)@[3].dom().contains(k__post2_self__tlb_mapping_2m___3__dom___contains)); }
    if g__post2_self__tlb_mapping_2m___4__dom___empty { assume((post2_self_.tlb_mapping_2m)@[4].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_2m___4__dom___lengt { assume((post2_self_.tlb_mapping_2m)@[4].dom().len() > 0); }
    if g__post2_self__tlb_mapping_2m___4__dom___leneq { assume((post2_self_.tlb_mapping_2m)@[4].dom().len() == k__post2_self__tlb_mapping_2m___4__dom___leneq); }
    if g__post2_self__tlb_mapping_2m___4__dom___lenrng { assume((post2_self_.tlb_mapping_2m)@[4].dom().len() >= k__post2_self__tlb_mapping_2m___4__dom___lenrng_lo && (post2_self_.tlb_mapping_2m)@[4].dom().len() <= k__post2_self__tlb_mapping_2m___4__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_2m___4__dom___contains { assume((post2_self_.tlb_mapping_2m)@[4].dom().contains(k__post2_self__tlb_mapping_2m___4__dom___contains)); }
    if g__post2_self__tlb_mapping_2m___5__dom___empty { assume((post2_self_.tlb_mapping_2m)@[5].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_2m___5__dom___lengt { assume((post2_self_.tlb_mapping_2m)@[5].dom().len() > 0); }
    if g__post2_self__tlb_mapping_2m___5__dom___leneq { assume((post2_self_.tlb_mapping_2m)@[5].dom().len() == k__post2_self__tlb_mapping_2m___5__dom___leneq); }
    if g__post2_self__tlb_mapping_2m___5__dom___lenrng { assume((post2_self_.tlb_mapping_2m)@[5].dom().len() >= k__post2_self__tlb_mapping_2m___5__dom___lenrng_lo && (post2_self_.tlb_mapping_2m)@[5].dom().len() <= k__post2_self__tlb_mapping_2m___5__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_2m___5__dom___contains { assume((post2_self_.tlb_mapping_2m)@[5].dom().contains(k__post2_self__tlb_mapping_2m___5__dom___contains)); }
    if g__post2_self__tlb_mapping_2m___6__dom___empty { assume((post2_self_.tlb_mapping_2m)@[6].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_2m___6__dom___lengt { assume((post2_self_.tlb_mapping_2m)@[6].dom().len() > 0); }
    if g__post2_self__tlb_mapping_2m___6__dom___leneq { assume((post2_self_.tlb_mapping_2m)@[6].dom().len() == k__post2_self__tlb_mapping_2m___6__dom___leneq); }
    if g__post2_self__tlb_mapping_2m___6__dom___lenrng { assume((post2_self_.tlb_mapping_2m)@[6].dom().len() >= k__post2_self__tlb_mapping_2m___6__dom___lenrng_lo && (post2_self_.tlb_mapping_2m)@[6].dom().len() <= k__post2_self__tlb_mapping_2m___6__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_2m___6__dom___contains { assume((post2_self_.tlb_mapping_2m)@[6].dom().contains(k__post2_self__tlb_mapping_2m___6__dom___contains)); }
    if g__post2_self__tlb_mapping_2m___7__dom___empty { assume((post2_self_.tlb_mapping_2m)@[7].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_2m___7__dom___lengt { assume((post2_self_.tlb_mapping_2m)@[7].dom().len() > 0); }
    if g__post2_self__tlb_mapping_2m___7__dom___leneq { assume((post2_self_.tlb_mapping_2m)@[7].dom().len() == k__post2_self__tlb_mapping_2m___7__dom___leneq); }
    if g__post2_self__tlb_mapping_2m___7__dom___lenrng { assume((post2_self_.tlb_mapping_2m)@[7].dom().len() >= k__post2_self__tlb_mapping_2m___7__dom___lenrng_lo && (post2_self_.tlb_mapping_2m)@[7].dom().len() <= k__post2_self__tlb_mapping_2m___7__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_2m___7__dom___contains { assume((post2_self_.tlb_mapping_2m)@[7].dom().contains(k__post2_self__tlb_mapping_2m___7__dom___contains)); }
    if g__post2_self__tlb_mapping_1g___leneq { assume((post2_self_.tlb_mapping_1g)@.len() == k__post2_self__tlb_mapping_1g___leneq); }
    if g__post2_self__tlb_mapping_1g___lenrng { assume((post2_self_.tlb_mapping_1g)@.len() >= k__post2_self__tlb_mapping_1g___lenrng_lo && (post2_self_.tlb_mapping_1g)@.len() <= k__post2_self__tlb_mapping_1g___lenrng_hi); }
    if g__post2_self__tlb_mapping_1g___0__dom___empty { assume((post2_self_.tlb_mapping_1g)@[0].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_1g___0__dom___lengt { assume((post2_self_.tlb_mapping_1g)@[0].dom().len() > 0); }
    if g__post2_self__tlb_mapping_1g___0__dom___leneq { assume((post2_self_.tlb_mapping_1g)@[0].dom().len() == k__post2_self__tlb_mapping_1g___0__dom___leneq); }
    if g__post2_self__tlb_mapping_1g___0__dom___lenrng { assume((post2_self_.tlb_mapping_1g)@[0].dom().len() >= k__post2_self__tlb_mapping_1g___0__dom___lenrng_lo && (post2_self_.tlb_mapping_1g)@[0].dom().len() <= k__post2_self__tlb_mapping_1g___0__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_1g___0__dom___contains { assume((post2_self_.tlb_mapping_1g)@[0].dom().contains(k__post2_self__tlb_mapping_1g___0__dom___contains)); }
    if g__post2_self__tlb_mapping_1g___1__dom___empty { assume((post2_self_.tlb_mapping_1g)@[1].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_1g___1__dom___lengt { assume((post2_self_.tlb_mapping_1g)@[1].dom().len() > 0); }
    if g__post2_self__tlb_mapping_1g___1__dom___leneq { assume((post2_self_.tlb_mapping_1g)@[1].dom().len() == k__post2_self__tlb_mapping_1g___1__dom___leneq); }
    if g__post2_self__tlb_mapping_1g___1__dom___lenrng { assume((post2_self_.tlb_mapping_1g)@[1].dom().len() >= k__post2_self__tlb_mapping_1g___1__dom___lenrng_lo && (post2_self_.tlb_mapping_1g)@[1].dom().len() <= k__post2_self__tlb_mapping_1g___1__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_1g___1__dom___contains { assume((post2_self_.tlb_mapping_1g)@[1].dom().contains(k__post2_self__tlb_mapping_1g___1__dom___contains)); }
    if g__post2_self__tlb_mapping_1g___2__dom___empty { assume((post2_self_.tlb_mapping_1g)@[2].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_1g___2__dom___lengt { assume((post2_self_.tlb_mapping_1g)@[2].dom().len() > 0); }
    if g__post2_self__tlb_mapping_1g___2__dom___leneq { assume((post2_self_.tlb_mapping_1g)@[2].dom().len() == k__post2_self__tlb_mapping_1g___2__dom___leneq); }
    if g__post2_self__tlb_mapping_1g___2__dom___lenrng { assume((post2_self_.tlb_mapping_1g)@[2].dom().len() >= k__post2_self__tlb_mapping_1g___2__dom___lenrng_lo && (post2_self_.tlb_mapping_1g)@[2].dom().len() <= k__post2_self__tlb_mapping_1g___2__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_1g___2__dom___contains { assume((post2_self_.tlb_mapping_1g)@[2].dom().contains(k__post2_self__tlb_mapping_1g___2__dom___contains)); }
    if g__post2_self__tlb_mapping_1g___3__dom___empty { assume((post2_self_.tlb_mapping_1g)@[3].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_1g___3__dom___lengt { assume((post2_self_.tlb_mapping_1g)@[3].dom().len() > 0); }
    if g__post2_self__tlb_mapping_1g___3__dom___leneq { assume((post2_self_.tlb_mapping_1g)@[3].dom().len() == k__post2_self__tlb_mapping_1g___3__dom___leneq); }
    if g__post2_self__tlb_mapping_1g___3__dom___lenrng { assume((post2_self_.tlb_mapping_1g)@[3].dom().len() >= k__post2_self__tlb_mapping_1g___3__dom___lenrng_lo && (post2_self_.tlb_mapping_1g)@[3].dom().len() <= k__post2_self__tlb_mapping_1g___3__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_1g___3__dom___contains { assume((post2_self_.tlb_mapping_1g)@[3].dom().contains(k__post2_self__tlb_mapping_1g___3__dom___contains)); }
    if g__post2_self__tlb_mapping_1g___4__dom___empty { assume((post2_self_.tlb_mapping_1g)@[4].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_1g___4__dom___lengt { assume((post2_self_.tlb_mapping_1g)@[4].dom().len() > 0); }
    if g__post2_self__tlb_mapping_1g___4__dom___leneq { assume((post2_self_.tlb_mapping_1g)@[4].dom().len() == k__post2_self__tlb_mapping_1g___4__dom___leneq); }
    if g__post2_self__tlb_mapping_1g___4__dom___lenrng { assume((post2_self_.tlb_mapping_1g)@[4].dom().len() >= k__post2_self__tlb_mapping_1g___4__dom___lenrng_lo && (post2_self_.tlb_mapping_1g)@[4].dom().len() <= k__post2_self__tlb_mapping_1g___4__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_1g___4__dom___contains { assume((post2_self_.tlb_mapping_1g)@[4].dom().contains(k__post2_self__tlb_mapping_1g___4__dom___contains)); }
    if g__post2_self__tlb_mapping_1g___5__dom___empty { assume((post2_self_.tlb_mapping_1g)@[5].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_1g___5__dom___lengt { assume((post2_self_.tlb_mapping_1g)@[5].dom().len() > 0); }
    if g__post2_self__tlb_mapping_1g___5__dom___leneq { assume((post2_self_.tlb_mapping_1g)@[5].dom().len() == k__post2_self__tlb_mapping_1g___5__dom___leneq); }
    if g__post2_self__tlb_mapping_1g___5__dom___lenrng { assume((post2_self_.tlb_mapping_1g)@[5].dom().len() >= k__post2_self__tlb_mapping_1g___5__dom___lenrng_lo && (post2_self_.tlb_mapping_1g)@[5].dom().len() <= k__post2_self__tlb_mapping_1g___5__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_1g___5__dom___contains { assume((post2_self_.tlb_mapping_1g)@[5].dom().contains(k__post2_self__tlb_mapping_1g___5__dom___contains)); }
    if g__post2_self__tlb_mapping_1g___6__dom___empty { assume((post2_self_.tlb_mapping_1g)@[6].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_1g___6__dom___lengt { assume((post2_self_.tlb_mapping_1g)@[6].dom().len() > 0); }
    if g__post2_self__tlb_mapping_1g___6__dom___leneq { assume((post2_self_.tlb_mapping_1g)@[6].dom().len() == k__post2_self__tlb_mapping_1g___6__dom___leneq); }
    if g__post2_self__tlb_mapping_1g___6__dom___lenrng { assume((post2_self_.tlb_mapping_1g)@[6].dom().len() >= k__post2_self__tlb_mapping_1g___6__dom___lenrng_lo && (post2_self_.tlb_mapping_1g)@[6].dom().len() <= k__post2_self__tlb_mapping_1g___6__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_1g___6__dom___contains { assume((post2_self_.tlb_mapping_1g)@[6].dom().contains(k__post2_self__tlb_mapping_1g___6__dom___contains)); }
    if g__post2_self__tlb_mapping_1g___7__dom___empty { assume((post2_self_.tlb_mapping_1g)@[7].dom() == Set::<VAddr>::empty()); }
    if g__post2_self__tlb_mapping_1g___7__dom___lengt { assume((post2_self_.tlb_mapping_1g)@[7].dom().len() > 0); }
    if g__post2_self__tlb_mapping_1g___7__dom___leneq { assume((post2_self_.tlb_mapping_1g)@[7].dom().len() == k__post2_self__tlb_mapping_1g___7__dom___leneq); }
    if g__post2_self__tlb_mapping_1g___7__dom___lenrng { assume((post2_self_.tlb_mapping_1g)@[7].dom().len() >= k__post2_self__tlb_mapping_1g___7__dom___lenrng_lo && (post2_self_.tlb_mapping_1g)@[7].dom().len() <= k__post2_self__tlb_mapping_1g___7__dom___lenrng_hi); }
    if g__post2_self__tlb_mapping_1g___7__dom___contains { assume((post2_self_.tlb_mapping_1g)@[7].dom().contains(k__post2_self__tlb_mapping_1g___7__dom___contains)); }
    if g_neq_tuple { assume(!det_map_4k_page_equal(r1, r2, post1_self_, post2_self_)); }
}
// === END INJECTED ===

}
