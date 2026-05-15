use vstd::prelude::*;

fn main() {}

verus!{

pub type PAddr = usize;

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

    pub open spec fn view(&self) -> Seq<PageEntry> {
        self.spec_seq@
    }

    pub fn set(&mut self, index: usize, value: PageEntry)
        requires
            old(self).wf(),
            0 <= index < 512,
            value.perm.present ==> MEM_valid(value.addr),
            value.perm.present == false ==> value.is_empty(),
        ensures
            self.wf(),
            self@ =~= old(self)@.update(index as int, value),
    {
        if value.perm.present == false {
            self.ar.set(index, 0usize);
            proof {
                zero_leads_is_empty_page_entry();
                self.spec_seq@ = self.spec_seq@.update(index as int, usize2page_entry(0usize));
            }
            return ;
        } else {
            let u = page_entry2usize(&value);
            self.ar.set(index, u);

            assert(usize2present(u) == value.perm.present);
            assert(usize2present(u) == true);
            assert(u != 0) by (bit_vector)
                requires
                    (u & 0x1u64 as usize) != 0 == true,
            ;

            proof {
                self.spec_seq@ = self.spec_seq@.update(index as int, value);
            }

            return ;
        }
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

	#[verifier::external_body]
pub proof fn zero_leads_is_empty_page_entry()
    ensures
        spec_usize2page_entry(0).is_empty(),
	{
		unimplemented!()
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

pub open spec fn spec_usize2page_entry(v: usize) -> PageEntry {
    PageEntry { addr: usize2pa(v), perm: usize2page_entry_perm(v) }
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


	#[verifier::external_body]
pub fn page_entry2usize(page_entry: &PageEntry) -> (ret: usize)
    requires
        MEM_valid(page_entry.addr),
    ensures
        usize2present(ret) == page_entry.perm.present,
        usize2ps(ret) == page_entry.perm.ps,
        usize2write(ret) == page_entry.perm.write,
        usize2execute_disable(ret) == page_entry.perm.execute_disable,
        usize2user(ret) == page_entry.perm.user,
        usize2pa(ret) == page_entry.addr,
        usize2page_entry_perm(ret) =~= page_entry.perm,
	{
		unimplemented!()
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


impl<A, const N: usize> Array<A, N> {

	#[verifier::external_body]
    #[verifier(external_body)]
    pub fn set(&mut self, i: usize, out: A)
        requires
            0 <= i < N,
            old(self).wf(),
        ensures
            self.seq@ =~= old(self).seq@.update(i as int, out),
            self.wf(),
	{
		unimplemented!()
	}

}



// File: util/page_ptr_util_u.rs
pub open spec fn MEM_valid(v: PAddr) -> bool {
    v & (!MEM_MASK) as usize == 0
}


// File: define.rs
pub const MEM_MASK: u64 = 0x0000_ffff_ffff_f000;

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
pub struct PageMapView { pub ar: Array<usize, 512>, pub spec_seq: Seq<PageEntry> }

impl View for PageMap {
    type V = PageMapView;
    closed spec fn view(&self) -> PageMapView {
        PageMapView { ar: self.ar, spec_seq: self.spec_seq@ }
    }
}

// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_set_equal(r1: (), r2: (), post1_self_: PageMap, post2_self_: PageMap) -> bool {
    (r1 == r2)
    && (((post1_self_).view() == (post2_self_).view()))
}

proof fn det_set(g__pre_self__spec_seq___leneq: bool, k__pre_self__spec_seq___leneq: nat, g__pre_self__spec_seq___lenrng: bool, k__pre_self__spec_seq___lenrng_lo: nat, k__pre_self__spec_seq___lenrng_hi: nat, g__pre_self__spec_seq___0__perm_present_is_true: bool, g__pre_self__spec_seq___0__perm_present_is_false: bool, g__pre_self__spec_seq___0__perm_ps_is_true: bool, g__pre_self__spec_seq___0__perm_ps_is_false: bool, g__pre_self__spec_seq___0__perm_write_is_true: bool, g__pre_self__spec_seq___0__perm_write_is_false: bool, g__pre_self__spec_seq___0__perm_execute_disable_is_true: bool, g__pre_self__spec_seq___0__perm_execute_disable_is_false: bool, g__pre_self__spec_seq___0__perm_user_is_true: bool, g__pre_self__spec_seq___0__perm_user_is_false: bool, g__pre_self__spec_seq___1__perm_present_is_true: bool, g__pre_self__spec_seq___1__perm_present_is_false: bool, g__pre_self__spec_seq___1__perm_ps_is_true: bool, g__pre_self__spec_seq___1__perm_ps_is_false: bool, g__pre_self__spec_seq___1__perm_write_is_true: bool, g__pre_self__spec_seq___1__perm_write_is_false: bool, g__pre_self__spec_seq___1__perm_execute_disable_is_true: bool, g__pre_self__spec_seq___1__perm_execute_disable_is_false: bool, g__pre_self__spec_seq___1__perm_user_is_true: bool, g__pre_self__spec_seq___1__perm_user_is_false: bool, g__pre_self__spec_seq___2__perm_present_is_true: bool, g__pre_self__spec_seq___2__perm_present_is_false: bool, g__pre_self__spec_seq___2__perm_ps_is_true: bool, g__pre_self__spec_seq___2__perm_ps_is_false: bool, g__pre_self__spec_seq___2__perm_write_is_true: bool, g__pre_self__spec_seq___2__perm_write_is_false: bool, g__pre_self__spec_seq___2__perm_execute_disable_is_true: bool, g__pre_self__spec_seq___2__perm_execute_disable_is_false: bool, g__pre_self__spec_seq___2__perm_user_is_true: bool, g__pre_self__spec_seq___2__perm_user_is_false: bool, g__pre_self__spec_seq___3__perm_present_is_true: bool, g__pre_self__spec_seq___3__perm_present_is_false: bool, g__pre_self__spec_seq___3__perm_ps_is_true: bool, g__pre_self__spec_seq___3__perm_ps_is_false: bool, g__pre_self__spec_seq___3__perm_write_is_true: bool, g__pre_self__spec_seq___3__perm_write_is_false: bool, g__pre_self__spec_seq___3__perm_execute_disable_is_true: bool, g__pre_self__spec_seq___3__perm_execute_disable_is_false: bool, g__pre_self__spec_seq___3__perm_user_is_true: bool, g__pre_self__spec_seq___3__perm_user_is_false: bool, g__pre_self__spec_seq___4__perm_present_is_true: bool, g__pre_self__spec_seq___4__perm_present_is_false: bool, g__pre_self__spec_seq___4__perm_ps_is_true: bool, g__pre_self__spec_seq___4__perm_ps_is_false: bool, g__pre_self__spec_seq___4__perm_write_is_true: bool, g__pre_self__spec_seq___4__perm_write_is_false: bool, g__pre_self__spec_seq___4__perm_execute_disable_is_true: bool, g__pre_self__spec_seq___4__perm_execute_disable_is_false: bool, g__pre_self__spec_seq___4__perm_user_is_true: bool, g__pre_self__spec_seq___4__perm_user_is_false: bool, g__pre_self__spec_seq___5__perm_present_is_true: bool, g__pre_self__spec_seq___5__perm_present_is_false: bool, g__pre_self__spec_seq___5__perm_ps_is_true: bool, g__pre_self__spec_seq___5__perm_ps_is_false: bool, g__pre_self__spec_seq___5__perm_write_is_true: bool, g__pre_self__spec_seq___5__perm_write_is_false: bool, g__pre_self__spec_seq___5__perm_execute_disable_is_true: bool, g__pre_self__spec_seq___5__perm_execute_disable_is_false: bool, g__pre_self__spec_seq___5__perm_user_is_true: bool, g__pre_self__spec_seq___5__perm_user_is_false: bool, g__pre_self__spec_seq___6__perm_present_is_true: bool, g__pre_self__spec_seq___6__perm_present_is_false: bool, g__pre_self__spec_seq___6__perm_ps_is_true: bool, g__pre_self__spec_seq___6__perm_ps_is_false: bool, g__pre_self__spec_seq___6__perm_write_is_true: bool, g__pre_self__spec_seq___6__perm_write_is_false: bool, g__pre_self__spec_seq___6__perm_execute_disable_is_true: bool, g__pre_self__spec_seq___6__perm_execute_disable_is_false: bool, g__pre_self__spec_seq___6__perm_user_is_true: bool, g__pre_self__spec_seq___6__perm_user_is_false: bool, g__pre_self__spec_seq___7__perm_present_is_true: bool, g__pre_self__spec_seq___7__perm_present_is_false: bool, g__pre_self__spec_seq___7__perm_ps_is_true: bool, g__pre_self__spec_seq___7__perm_ps_is_false: bool, g__pre_self__spec_seq___7__perm_write_is_true: bool, g__pre_self__spec_seq___7__perm_write_is_false: bool, g__pre_self__spec_seq___7__perm_execute_disable_is_true: bool, g__pre_self__spec_seq___7__perm_execute_disable_is_false: bool, g__pre_self__spec_seq___7__perm_user_is_true: bool, g__pre_self__spec_seq___7__perm_user_is_false: bool, g_index_eq: bool, k_index_eq: int, g_index_rng: bool, k_index_rng_lo: int, k_index_rng_hi: int, g_value_perm_present_is_true: bool, g_value_perm_present_is_false: bool, g_value_perm_ps_is_true: bool, g_value_perm_ps_is_false: bool, g_value_perm_write_is_true: bool, g_value_perm_write_is_false: bool, g_value_perm_execute_disable_is_true: bool, g_value_perm_execute_disable_is_false: bool, g_value_perm_user_is_true: bool, g_value_perm_user_is_false: bool, g__post1_self__spec_seq___leneq: bool, k__post1_self__spec_seq___leneq: nat, g__post1_self__spec_seq___lenrng: bool, k__post1_self__spec_seq___lenrng_lo: nat, k__post1_self__spec_seq___lenrng_hi: nat, g__post1_self__spec_seq___0__perm_present_is_true: bool, g__post1_self__spec_seq___0__perm_present_is_false: bool, g__post1_self__spec_seq___0__perm_ps_is_true: bool, g__post1_self__spec_seq___0__perm_ps_is_false: bool, g__post1_self__spec_seq___0__perm_write_is_true: bool, g__post1_self__spec_seq___0__perm_write_is_false: bool, g__post1_self__spec_seq___0__perm_execute_disable_is_true: bool, g__post1_self__spec_seq___0__perm_execute_disable_is_false: bool, g__post1_self__spec_seq___0__perm_user_is_true: bool, g__post1_self__spec_seq___0__perm_user_is_false: bool, g__post1_self__spec_seq___1__perm_present_is_true: bool, g__post1_self__spec_seq___1__perm_present_is_false: bool, g__post1_self__spec_seq___1__perm_ps_is_true: bool, g__post1_self__spec_seq___1__perm_ps_is_false: bool, g__post1_self__spec_seq___1__perm_write_is_true: bool, g__post1_self__spec_seq___1__perm_write_is_false: bool, g__post1_self__spec_seq___1__perm_execute_disable_is_true: bool, g__post1_self__spec_seq___1__perm_execute_disable_is_false: bool, g__post1_self__spec_seq___1__perm_user_is_true: bool, g__post1_self__spec_seq___1__perm_user_is_false: bool, g__post1_self__spec_seq___2__perm_present_is_true: bool, g__post1_self__spec_seq___2__perm_present_is_false: bool, g__post1_self__spec_seq___2__perm_ps_is_true: bool, g__post1_self__spec_seq___2__perm_ps_is_false: bool, g__post1_self__spec_seq___2__perm_write_is_true: bool, g__post1_self__spec_seq___2__perm_write_is_false: bool, g__post1_self__spec_seq___2__perm_execute_disable_is_true: bool, g__post1_self__spec_seq___2__perm_execute_disable_is_false: bool, g__post1_self__spec_seq___2__perm_user_is_true: bool, g__post1_self__spec_seq___2__perm_user_is_false: bool, g__post1_self__spec_seq___3__perm_present_is_true: bool, g__post1_self__spec_seq___3__perm_present_is_false: bool, g__post1_self__spec_seq___3__perm_ps_is_true: bool, g__post1_self__spec_seq___3__perm_ps_is_false: bool, g__post1_self__spec_seq___3__perm_write_is_true: bool, g__post1_self__spec_seq___3__perm_write_is_false: bool, g__post1_self__spec_seq___3__perm_execute_disable_is_true: bool, g__post1_self__spec_seq___3__perm_execute_disable_is_false: bool, g__post1_self__spec_seq___3__perm_user_is_true: bool, g__post1_self__spec_seq___3__perm_user_is_false: bool, g__post1_self__spec_seq___4__perm_present_is_true: bool, g__post1_self__spec_seq___4__perm_present_is_false: bool, g__post1_self__spec_seq___4__perm_ps_is_true: bool, g__post1_self__spec_seq___4__perm_ps_is_false: bool, g__post1_self__spec_seq___4__perm_write_is_true: bool, g__post1_self__spec_seq___4__perm_write_is_false: bool, g__post1_self__spec_seq___4__perm_execute_disable_is_true: bool, g__post1_self__spec_seq___4__perm_execute_disable_is_false: bool, g__post1_self__spec_seq___4__perm_user_is_true: bool, g__post1_self__spec_seq___4__perm_user_is_false: bool, g__post1_self__spec_seq___5__perm_present_is_true: bool, g__post1_self__spec_seq___5__perm_present_is_false: bool, g__post1_self__spec_seq___5__perm_ps_is_true: bool, g__post1_self__spec_seq___5__perm_ps_is_false: bool, g__post1_self__spec_seq___5__perm_write_is_true: bool, g__post1_self__spec_seq___5__perm_write_is_false: bool, g__post1_self__spec_seq___5__perm_execute_disable_is_true: bool, g__post1_self__spec_seq___5__perm_execute_disable_is_false: bool, g__post1_self__spec_seq___5__perm_user_is_true: bool, g__post1_self__spec_seq___5__perm_user_is_false: bool, g__post1_self__spec_seq___6__perm_present_is_true: bool, g__post1_self__spec_seq___6__perm_present_is_false: bool, g__post1_self__spec_seq___6__perm_ps_is_true: bool, g__post1_self__spec_seq___6__perm_ps_is_false: bool, g__post1_self__spec_seq___6__perm_write_is_true: bool, g__post1_self__spec_seq___6__perm_write_is_false: bool, g__post1_self__spec_seq___6__perm_execute_disable_is_true: bool, g__post1_self__spec_seq___6__perm_execute_disable_is_false: bool, g__post1_self__spec_seq___6__perm_user_is_true: bool, g__post1_self__spec_seq___6__perm_user_is_false: bool, g__post1_self__spec_seq___7__perm_present_is_true: bool, g__post1_self__spec_seq___7__perm_present_is_false: bool, g__post1_self__spec_seq___7__perm_ps_is_true: bool, g__post1_self__spec_seq___7__perm_ps_is_false: bool, g__post1_self__spec_seq___7__perm_write_is_true: bool, g__post1_self__spec_seq___7__perm_write_is_false: bool, g__post1_self__spec_seq___7__perm_execute_disable_is_true: bool, g__post1_self__spec_seq___7__perm_execute_disable_is_false: bool, g__post1_self__spec_seq___7__perm_user_is_true: bool, g__post1_self__spec_seq___7__perm_user_is_false: bool, g__post2_self__spec_seq___leneq: bool, k__post2_self__spec_seq___leneq: nat, g__post2_self__spec_seq___lenrng: bool, k__post2_self__spec_seq___lenrng_lo: nat, k__post2_self__spec_seq___lenrng_hi: nat, g__post2_self__spec_seq___0__perm_present_is_true: bool, g__post2_self__spec_seq___0__perm_present_is_false: bool, g__post2_self__spec_seq___0__perm_ps_is_true: bool, g__post2_self__spec_seq___0__perm_ps_is_false: bool, g__post2_self__spec_seq___0__perm_write_is_true: bool, g__post2_self__spec_seq___0__perm_write_is_false: bool, g__post2_self__spec_seq___0__perm_execute_disable_is_true: bool, g__post2_self__spec_seq___0__perm_execute_disable_is_false: bool, g__post2_self__spec_seq___0__perm_user_is_true: bool, g__post2_self__spec_seq___0__perm_user_is_false: bool, g__post2_self__spec_seq___1__perm_present_is_true: bool, g__post2_self__spec_seq___1__perm_present_is_false: bool, g__post2_self__spec_seq___1__perm_ps_is_true: bool, g__post2_self__spec_seq___1__perm_ps_is_false: bool, g__post2_self__spec_seq___1__perm_write_is_true: bool, g__post2_self__spec_seq___1__perm_write_is_false: bool, g__post2_self__spec_seq___1__perm_execute_disable_is_true: bool, g__post2_self__spec_seq___1__perm_execute_disable_is_false: bool, g__post2_self__spec_seq___1__perm_user_is_true: bool, g__post2_self__spec_seq___1__perm_user_is_false: bool, g__post2_self__spec_seq___2__perm_present_is_true: bool, g__post2_self__spec_seq___2__perm_present_is_false: bool, g__post2_self__spec_seq___2__perm_ps_is_true: bool, g__post2_self__spec_seq___2__perm_ps_is_false: bool, g__post2_self__spec_seq___2__perm_write_is_true: bool, g__post2_self__spec_seq___2__perm_write_is_false: bool, g__post2_self__spec_seq___2__perm_execute_disable_is_true: bool, g__post2_self__spec_seq___2__perm_execute_disable_is_false: bool, g__post2_self__spec_seq___2__perm_user_is_true: bool, g__post2_self__spec_seq___2__perm_user_is_false: bool, g__post2_self__spec_seq___3__perm_present_is_true: bool, g__post2_self__spec_seq___3__perm_present_is_false: bool, g__post2_self__spec_seq___3__perm_ps_is_true: bool, g__post2_self__spec_seq___3__perm_ps_is_false: bool, g__post2_self__spec_seq___3__perm_write_is_true: bool, g__post2_self__spec_seq___3__perm_write_is_false: bool, g__post2_self__spec_seq___3__perm_execute_disable_is_true: bool, g__post2_self__spec_seq___3__perm_execute_disable_is_false: bool, g__post2_self__spec_seq___3__perm_user_is_true: bool, g__post2_self__spec_seq___3__perm_user_is_false: bool, g__post2_self__spec_seq___4__perm_present_is_true: bool, g__post2_self__spec_seq___4__perm_present_is_false: bool, g__post2_self__spec_seq___4__perm_ps_is_true: bool, g__post2_self__spec_seq___4__perm_ps_is_false: bool, g__post2_self__spec_seq___4__perm_write_is_true: bool, g__post2_self__spec_seq___4__perm_write_is_false: bool, g__post2_self__spec_seq___4__perm_execute_disable_is_true: bool, g__post2_self__spec_seq___4__perm_execute_disable_is_false: bool, g__post2_self__spec_seq___4__perm_user_is_true: bool, g__post2_self__spec_seq___4__perm_user_is_false: bool, g__post2_self__spec_seq___5__perm_present_is_true: bool, g__post2_self__spec_seq___5__perm_present_is_false: bool, g__post2_self__spec_seq___5__perm_ps_is_true: bool, g__post2_self__spec_seq___5__perm_ps_is_false: bool, g__post2_self__spec_seq___5__perm_write_is_true: bool, g__post2_self__spec_seq___5__perm_write_is_false: bool, g__post2_self__spec_seq___5__perm_execute_disable_is_true: bool, g__post2_self__spec_seq___5__perm_execute_disable_is_false: bool, g__post2_self__spec_seq___5__perm_user_is_true: bool, g__post2_self__spec_seq___5__perm_user_is_false: bool, g__post2_self__spec_seq___6__perm_present_is_true: bool, g__post2_self__spec_seq___6__perm_present_is_false: bool, g__post2_self__spec_seq___6__perm_ps_is_true: bool, g__post2_self__spec_seq___6__perm_ps_is_false: bool, g__post2_self__spec_seq___6__perm_write_is_true: bool, g__post2_self__spec_seq___6__perm_write_is_false: bool, g__post2_self__spec_seq___6__perm_execute_disable_is_true: bool, g__post2_self__spec_seq___6__perm_execute_disable_is_false: bool, g__post2_self__spec_seq___6__perm_user_is_true: bool, g__post2_self__spec_seq___6__perm_user_is_false: bool, g__post2_self__spec_seq___7__perm_present_is_true: bool, g__post2_self__spec_seq___7__perm_present_is_false: bool, g__post2_self__spec_seq___7__perm_ps_is_true: bool, g__post2_self__spec_seq___7__perm_ps_is_false: bool, g__post2_self__spec_seq___7__perm_write_is_true: bool, g__post2_self__spec_seq___7__perm_write_is_false: bool, g__post2_self__spec_seq___7__perm_execute_disable_is_true: bool, g__post2_self__spec_seq___7__perm_execute_disable_is_false: bool, g__post2_self__spec_seq___7__perm_user_is_true: bool, g__post2_self__spec_seq___7__perm_user_is_false: bool, g_neq_tuple: bool, pre_self_: PageMap, index: usize, value: PageEntry, post1_self_: PageMap, r1: (), post2_self_: PageMap, r2: ())
    requires (pre_self_.wf()), (0 <= index < 512), (value.perm.present ==> MEM_valid(value.addr)), (value.perm.present == false ==> value.is_empty()),
    ensures
        ({
            &&& (post1_self_.wf())
            &&& (post1_self_@ =~= pre_self_@.update(index as int, value))
            &&& (post2_self_.wf())
            &&& (post2_self_@ =~= pre_self_@.update(index as int, value))
        }) ==> det_set_equal(r1, r2, post1_self_, post2_self_),
{
    if g__pre_self__spec_seq___leneq { assume((pre_self_.spec_seq)@.len() == k__pre_self__spec_seq___leneq); }
    if g__pre_self__spec_seq___lenrng { assume((pre_self_.spec_seq)@.len() >= k__pre_self__spec_seq___lenrng_lo && (pre_self_.spec_seq)@.len() <= k__pre_self__spec_seq___lenrng_hi); }
    if g__pre_self__spec_seq___0__perm_present_is_true { assume((pre_self_.spec_seq)@[0].perm.present == true); }
    if g__pre_self__spec_seq___0__perm_present_is_false { assume((pre_self_.spec_seq)@[0].perm.present == false); }
    if g__pre_self__spec_seq___0__perm_ps_is_true { assume((pre_self_.spec_seq)@[0].perm.ps == true); }
    if g__pre_self__spec_seq___0__perm_ps_is_false { assume((pre_self_.spec_seq)@[0].perm.ps == false); }
    if g__pre_self__spec_seq___0__perm_write_is_true { assume((pre_self_.spec_seq)@[0].perm.write == true); }
    if g__pre_self__spec_seq___0__perm_write_is_false { assume((pre_self_.spec_seq)@[0].perm.write == false); }
    if g__pre_self__spec_seq___0__perm_execute_disable_is_true { assume((pre_self_.spec_seq)@[0].perm.execute_disable == true); }
    if g__pre_self__spec_seq___0__perm_execute_disable_is_false { assume((pre_self_.spec_seq)@[0].perm.execute_disable == false); }
    if g__pre_self__spec_seq___0__perm_user_is_true { assume((pre_self_.spec_seq)@[0].perm.user == true); }
    if g__pre_self__spec_seq___0__perm_user_is_false { assume((pre_self_.spec_seq)@[0].perm.user == false); }
    if g__pre_self__spec_seq___1__perm_present_is_true { assume((pre_self_.spec_seq)@[1].perm.present == true); }
    if g__pre_self__spec_seq___1__perm_present_is_false { assume((pre_self_.spec_seq)@[1].perm.present == false); }
    if g__pre_self__spec_seq___1__perm_ps_is_true { assume((pre_self_.spec_seq)@[1].perm.ps == true); }
    if g__pre_self__spec_seq___1__perm_ps_is_false { assume((pre_self_.spec_seq)@[1].perm.ps == false); }
    if g__pre_self__spec_seq___1__perm_write_is_true { assume((pre_self_.spec_seq)@[1].perm.write == true); }
    if g__pre_self__spec_seq___1__perm_write_is_false { assume((pre_self_.spec_seq)@[1].perm.write == false); }
    if g__pre_self__spec_seq___1__perm_execute_disable_is_true { assume((pre_self_.spec_seq)@[1].perm.execute_disable == true); }
    if g__pre_self__spec_seq___1__perm_execute_disable_is_false { assume((pre_self_.spec_seq)@[1].perm.execute_disable == false); }
    if g__pre_self__spec_seq___1__perm_user_is_true { assume((pre_self_.spec_seq)@[1].perm.user == true); }
    if g__pre_self__spec_seq___1__perm_user_is_false { assume((pre_self_.spec_seq)@[1].perm.user == false); }
    if g__pre_self__spec_seq___2__perm_present_is_true { assume((pre_self_.spec_seq)@[2].perm.present == true); }
    if g__pre_self__spec_seq___2__perm_present_is_false { assume((pre_self_.spec_seq)@[2].perm.present == false); }
    if g__pre_self__spec_seq___2__perm_ps_is_true { assume((pre_self_.spec_seq)@[2].perm.ps == true); }
    if g__pre_self__spec_seq___2__perm_ps_is_false { assume((pre_self_.spec_seq)@[2].perm.ps == false); }
    if g__pre_self__spec_seq___2__perm_write_is_true { assume((pre_self_.spec_seq)@[2].perm.write == true); }
    if g__pre_self__spec_seq___2__perm_write_is_false { assume((pre_self_.spec_seq)@[2].perm.write == false); }
    if g__pre_self__spec_seq___2__perm_execute_disable_is_true { assume((pre_self_.spec_seq)@[2].perm.execute_disable == true); }
    if g__pre_self__spec_seq___2__perm_execute_disable_is_false { assume((pre_self_.spec_seq)@[2].perm.execute_disable == false); }
    if g__pre_self__spec_seq___2__perm_user_is_true { assume((pre_self_.spec_seq)@[2].perm.user == true); }
    if g__pre_self__spec_seq___2__perm_user_is_false { assume((pre_self_.spec_seq)@[2].perm.user == false); }
    if g__pre_self__spec_seq___3__perm_present_is_true { assume((pre_self_.spec_seq)@[3].perm.present == true); }
    if g__pre_self__spec_seq___3__perm_present_is_false { assume((pre_self_.spec_seq)@[3].perm.present == false); }
    if g__pre_self__spec_seq___3__perm_ps_is_true { assume((pre_self_.spec_seq)@[3].perm.ps == true); }
    if g__pre_self__spec_seq___3__perm_ps_is_false { assume((pre_self_.spec_seq)@[3].perm.ps == false); }
    if g__pre_self__spec_seq___3__perm_write_is_true { assume((pre_self_.spec_seq)@[3].perm.write == true); }
    if g__pre_self__spec_seq___3__perm_write_is_false { assume((pre_self_.spec_seq)@[3].perm.write == false); }
    if g__pre_self__spec_seq___3__perm_execute_disable_is_true { assume((pre_self_.spec_seq)@[3].perm.execute_disable == true); }
    if g__pre_self__spec_seq___3__perm_execute_disable_is_false { assume((pre_self_.spec_seq)@[3].perm.execute_disable == false); }
    if g__pre_self__spec_seq___3__perm_user_is_true { assume((pre_self_.spec_seq)@[3].perm.user == true); }
    if g__pre_self__spec_seq___3__perm_user_is_false { assume((pre_self_.spec_seq)@[3].perm.user == false); }
    if g__pre_self__spec_seq___4__perm_present_is_true { assume((pre_self_.spec_seq)@[4].perm.present == true); }
    if g__pre_self__spec_seq___4__perm_present_is_false { assume((pre_self_.spec_seq)@[4].perm.present == false); }
    if g__pre_self__spec_seq___4__perm_ps_is_true { assume((pre_self_.spec_seq)@[4].perm.ps == true); }
    if g__pre_self__spec_seq___4__perm_ps_is_false { assume((pre_self_.spec_seq)@[4].perm.ps == false); }
    if g__pre_self__spec_seq___4__perm_write_is_true { assume((pre_self_.spec_seq)@[4].perm.write == true); }
    if g__pre_self__spec_seq___4__perm_write_is_false { assume((pre_self_.spec_seq)@[4].perm.write == false); }
    if g__pre_self__spec_seq___4__perm_execute_disable_is_true { assume((pre_self_.spec_seq)@[4].perm.execute_disable == true); }
    if g__pre_self__spec_seq___4__perm_execute_disable_is_false { assume((pre_self_.spec_seq)@[4].perm.execute_disable == false); }
    if g__pre_self__spec_seq___4__perm_user_is_true { assume((pre_self_.spec_seq)@[4].perm.user == true); }
    if g__pre_self__spec_seq___4__perm_user_is_false { assume((pre_self_.spec_seq)@[4].perm.user == false); }
    if g__pre_self__spec_seq___5__perm_present_is_true { assume((pre_self_.spec_seq)@[5].perm.present == true); }
    if g__pre_self__spec_seq___5__perm_present_is_false { assume((pre_self_.spec_seq)@[5].perm.present == false); }
    if g__pre_self__spec_seq___5__perm_ps_is_true { assume((pre_self_.spec_seq)@[5].perm.ps == true); }
    if g__pre_self__spec_seq___5__perm_ps_is_false { assume((pre_self_.spec_seq)@[5].perm.ps == false); }
    if g__pre_self__spec_seq___5__perm_write_is_true { assume((pre_self_.spec_seq)@[5].perm.write == true); }
    if g__pre_self__spec_seq___5__perm_write_is_false { assume((pre_self_.spec_seq)@[5].perm.write == false); }
    if g__pre_self__spec_seq___5__perm_execute_disable_is_true { assume((pre_self_.spec_seq)@[5].perm.execute_disable == true); }
    if g__pre_self__spec_seq___5__perm_execute_disable_is_false { assume((pre_self_.spec_seq)@[5].perm.execute_disable == false); }
    if g__pre_self__spec_seq___5__perm_user_is_true { assume((pre_self_.spec_seq)@[5].perm.user == true); }
    if g__pre_self__spec_seq___5__perm_user_is_false { assume((pre_self_.spec_seq)@[5].perm.user == false); }
    if g__pre_self__spec_seq___6__perm_present_is_true { assume((pre_self_.spec_seq)@[6].perm.present == true); }
    if g__pre_self__spec_seq___6__perm_present_is_false { assume((pre_self_.spec_seq)@[6].perm.present == false); }
    if g__pre_self__spec_seq___6__perm_ps_is_true { assume((pre_self_.spec_seq)@[6].perm.ps == true); }
    if g__pre_self__spec_seq___6__perm_ps_is_false { assume((pre_self_.spec_seq)@[6].perm.ps == false); }
    if g__pre_self__spec_seq___6__perm_write_is_true { assume((pre_self_.spec_seq)@[6].perm.write == true); }
    if g__pre_self__spec_seq___6__perm_write_is_false { assume((pre_self_.spec_seq)@[6].perm.write == false); }
    if g__pre_self__spec_seq___6__perm_execute_disable_is_true { assume((pre_self_.spec_seq)@[6].perm.execute_disable == true); }
    if g__pre_self__spec_seq___6__perm_execute_disable_is_false { assume((pre_self_.spec_seq)@[6].perm.execute_disable == false); }
    if g__pre_self__spec_seq___6__perm_user_is_true { assume((pre_self_.spec_seq)@[6].perm.user == true); }
    if g__pre_self__spec_seq___6__perm_user_is_false { assume((pre_self_.spec_seq)@[6].perm.user == false); }
    if g__pre_self__spec_seq___7__perm_present_is_true { assume((pre_self_.spec_seq)@[7].perm.present == true); }
    if g__pre_self__spec_seq___7__perm_present_is_false { assume((pre_self_.spec_seq)@[7].perm.present == false); }
    if g__pre_self__spec_seq___7__perm_ps_is_true { assume((pre_self_.spec_seq)@[7].perm.ps == true); }
    if g__pre_self__spec_seq___7__perm_ps_is_false { assume((pre_self_.spec_seq)@[7].perm.ps == false); }
    if g__pre_self__spec_seq___7__perm_write_is_true { assume((pre_self_.spec_seq)@[7].perm.write == true); }
    if g__pre_self__spec_seq___7__perm_write_is_false { assume((pre_self_.spec_seq)@[7].perm.write == false); }
    if g__pre_self__spec_seq___7__perm_execute_disable_is_true { assume((pre_self_.spec_seq)@[7].perm.execute_disable == true); }
    if g__pre_self__spec_seq___7__perm_execute_disable_is_false { assume((pre_self_.spec_seq)@[7].perm.execute_disable == false); }
    if g__pre_self__spec_seq___7__perm_user_is_true { assume((pre_self_.spec_seq)@[7].perm.user == true); }
    if g__pre_self__spec_seq___7__perm_user_is_false { assume((pre_self_.spec_seq)@[7].perm.user == false); }
    if g_index_eq { assume(index as int == k_index_eq); }
    if g_index_rng { assume(index as int >= k_index_rng_lo && index as int <= k_index_rng_hi); }
    if g_value_perm_present_is_true { assume(value.perm.present == true); }
    if g_value_perm_present_is_false { assume(value.perm.present == false); }
    if g_value_perm_ps_is_true { assume(value.perm.ps == true); }
    if g_value_perm_ps_is_false { assume(value.perm.ps == false); }
    if g_value_perm_write_is_true { assume(value.perm.write == true); }
    if g_value_perm_write_is_false { assume(value.perm.write == false); }
    if g_value_perm_execute_disable_is_true { assume(value.perm.execute_disable == true); }
    if g_value_perm_execute_disable_is_false { assume(value.perm.execute_disable == false); }
    if g_value_perm_user_is_true { assume(value.perm.user == true); }
    if g_value_perm_user_is_false { assume(value.perm.user == false); }
    if g__post1_self__spec_seq___leneq { assume((post1_self_.spec_seq)@.len() == k__post1_self__spec_seq___leneq); }
    if g__post1_self__spec_seq___lenrng { assume((post1_self_.spec_seq)@.len() >= k__post1_self__spec_seq___lenrng_lo && (post1_self_.spec_seq)@.len() <= k__post1_self__spec_seq___lenrng_hi); }
    if g__post1_self__spec_seq___0__perm_present_is_true { assume((post1_self_.spec_seq)@[0].perm.present == true); }
    if g__post1_self__spec_seq___0__perm_present_is_false { assume((post1_self_.spec_seq)@[0].perm.present == false); }
    if g__post1_self__spec_seq___0__perm_ps_is_true { assume((post1_self_.spec_seq)@[0].perm.ps == true); }
    if g__post1_self__spec_seq___0__perm_ps_is_false { assume((post1_self_.spec_seq)@[0].perm.ps == false); }
    if g__post1_self__spec_seq___0__perm_write_is_true { assume((post1_self_.spec_seq)@[0].perm.write == true); }
    if g__post1_self__spec_seq___0__perm_write_is_false { assume((post1_self_.spec_seq)@[0].perm.write == false); }
    if g__post1_self__spec_seq___0__perm_execute_disable_is_true { assume((post1_self_.spec_seq)@[0].perm.execute_disable == true); }
    if g__post1_self__spec_seq___0__perm_execute_disable_is_false { assume((post1_self_.spec_seq)@[0].perm.execute_disable == false); }
    if g__post1_self__spec_seq___0__perm_user_is_true { assume((post1_self_.spec_seq)@[0].perm.user == true); }
    if g__post1_self__spec_seq___0__perm_user_is_false { assume((post1_self_.spec_seq)@[0].perm.user == false); }
    if g__post1_self__spec_seq___1__perm_present_is_true { assume((post1_self_.spec_seq)@[1].perm.present == true); }
    if g__post1_self__spec_seq___1__perm_present_is_false { assume((post1_self_.spec_seq)@[1].perm.present == false); }
    if g__post1_self__spec_seq___1__perm_ps_is_true { assume((post1_self_.spec_seq)@[1].perm.ps == true); }
    if g__post1_self__spec_seq___1__perm_ps_is_false { assume((post1_self_.spec_seq)@[1].perm.ps == false); }
    if g__post1_self__spec_seq___1__perm_write_is_true { assume((post1_self_.spec_seq)@[1].perm.write == true); }
    if g__post1_self__spec_seq___1__perm_write_is_false { assume((post1_self_.spec_seq)@[1].perm.write == false); }
    if g__post1_self__spec_seq___1__perm_execute_disable_is_true { assume((post1_self_.spec_seq)@[1].perm.execute_disable == true); }
    if g__post1_self__spec_seq___1__perm_execute_disable_is_false { assume((post1_self_.spec_seq)@[1].perm.execute_disable == false); }
    if g__post1_self__spec_seq___1__perm_user_is_true { assume((post1_self_.spec_seq)@[1].perm.user == true); }
    if g__post1_self__spec_seq___1__perm_user_is_false { assume((post1_self_.spec_seq)@[1].perm.user == false); }
    if g__post1_self__spec_seq___2__perm_present_is_true { assume((post1_self_.spec_seq)@[2].perm.present == true); }
    if g__post1_self__spec_seq___2__perm_present_is_false { assume((post1_self_.spec_seq)@[2].perm.present == false); }
    if g__post1_self__spec_seq___2__perm_ps_is_true { assume((post1_self_.spec_seq)@[2].perm.ps == true); }
    if g__post1_self__spec_seq___2__perm_ps_is_false { assume((post1_self_.spec_seq)@[2].perm.ps == false); }
    if g__post1_self__spec_seq___2__perm_write_is_true { assume((post1_self_.spec_seq)@[2].perm.write == true); }
    if g__post1_self__spec_seq___2__perm_write_is_false { assume((post1_self_.spec_seq)@[2].perm.write == false); }
    if g__post1_self__spec_seq___2__perm_execute_disable_is_true { assume((post1_self_.spec_seq)@[2].perm.execute_disable == true); }
    if g__post1_self__spec_seq___2__perm_execute_disable_is_false { assume((post1_self_.spec_seq)@[2].perm.execute_disable == false); }
    if g__post1_self__spec_seq___2__perm_user_is_true { assume((post1_self_.spec_seq)@[2].perm.user == true); }
    if g__post1_self__spec_seq___2__perm_user_is_false { assume((post1_self_.spec_seq)@[2].perm.user == false); }
    if g__post1_self__spec_seq___3__perm_present_is_true { assume((post1_self_.spec_seq)@[3].perm.present == true); }
    if g__post1_self__spec_seq___3__perm_present_is_false { assume((post1_self_.spec_seq)@[3].perm.present == false); }
    if g__post1_self__spec_seq___3__perm_ps_is_true { assume((post1_self_.spec_seq)@[3].perm.ps == true); }
    if g__post1_self__spec_seq___3__perm_ps_is_false { assume((post1_self_.spec_seq)@[3].perm.ps == false); }
    if g__post1_self__spec_seq___3__perm_write_is_true { assume((post1_self_.spec_seq)@[3].perm.write == true); }
    if g__post1_self__spec_seq___3__perm_write_is_false { assume((post1_self_.spec_seq)@[3].perm.write == false); }
    if g__post1_self__spec_seq___3__perm_execute_disable_is_true { assume((post1_self_.spec_seq)@[3].perm.execute_disable == true); }
    if g__post1_self__spec_seq___3__perm_execute_disable_is_false { assume((post1_self_.spec_seq)@[3].perm.execute_disable == false); }
    if g__post1_self__spec_seq___3__perm_user_is_true { assume((post1_self_.spec_seq)@[3].perm.user == true); }
    if g__post1_self__spec_seq___3__perm_user_is_false { assume((post1_self_.spec_seq)@[3].perm.user == false); }
    if g__post1_self__spec_seq___4__perm_present_is_true { assume((post1_self_.spec_seq)@[4].perm.present == true); }
    if g__post1_self__spec_seq___4__perm_present_is_false { assume((post1_self_.spec_seq)@[4].perm.present == false); }
    if g__post1_self__spec_seq___4__perm_ps_is_true { assume((post1_self_.spec_seq)@[4].perm.ps == true); }
    if g__post1_self__spec_seq___4__perm_ps_is_false { assume((post1_self_.spec_seq)@[4].perm.ps == false); }
    if g__post1_self__spec_seq___4__perm_write_is_true { assume((post1_self_.spec_seq)@[4].perm.write == true); }
    if g__post1_self__spec_seq___4__perm_write_is_false { assume((post1_self_.spec_seq)@[4].perm.write == false); }
    if g__post1_self__spec_seq___4__perm_execute_disable_is_true { assume((post1_self_.spec_seq)@[4].perm.execute_disable == true); }
    if g__post1_self__spec_seq___4__perm_execute_disable_is_false { assume((post1_self_.spec_seq)@[4].perm.execute_disable == false); }
    if g__post1_self__spec_seq___4__perm_user_is_true { assume((post1_self_.spec_seq)@[4].perm.user == true); }
    if g__post1_self__spec_seq___4__perm_user_is_false { assume((post1_self_.spec_seq)@[4].perm.user == false); }
    if g__post1_self__spec_seq___5__perm_present_is_true { assume((post1_self_.spec_seq)@[5].perm.present == true); }
    if g__post1_self__spec_seq___5__perm_present_is_false { assume((post1_self_.spec_seq)@[5].perm.present == false); }
    if g__post1_self__spec_seq___5__perm_ps_is_true { assume((post1_self_.spec_seq)@[5].perm.ps == true); }
    if g__post1_self__spec_seq___5__perm_ps_is_false { assume((post1_self_.spec_seq)@[5].perm.ps == false); }
    if g__post1_self__spec_seq___5__perm_write_is_true { assume((post1_self_.spec_seq)@[5].perm.write == true); }
    if g__post1_self__spec_seq___5__perm_write_is_false { assume((post1_self_.spec_seq)@[5].perm.write == false); }
    if g__post1_self__spec_seq___5__perm_execute_disable_is_true { assume((post1_self_.spec_seq)@[5].perm.execute_disable == true); }
    if g__post1_self__spec_seq___5__perm_execute_disable_is_false { assume((post1_self_.spec_seq)@[5].perm.execute_disable == false); }
    if g__post1_self__spec_seq___5__perm_user_is_true { assume((post1_self_.spec_seq)@[5].perm.user == true); }
    if g__post1_self__spec_seq___5__perm_user_is_false { assume((post1_self_.spec_seq)@[5].perm.user == false); }
    if g__post1_self__spec_seq___6__perm_present_is_true { assume((post1_self_.spec_seq)@[6].perm.present == true); }
    if g__post1_self__spec_seq___6__perm_present_is_false { assume((post1_self_.spec_seq)@[6].perm.present == false); }
    if g__post1_self__spec_seq___6__perm_ps_is_true { assume((post1_self_.spec_seq)@[6].perm.ps == true); }
    if g__post1_self__spec_seq___6__perm_ps_is_false { assume((post1_self_.spec_seq)@[6].perm.ps == false); }
    if g__post1_self__spec_seq___6__perm_write_is_true { assume((post1_self_.spec_seq)@[6].perm.write == true); }
    if g__post1_self__spec_seq___6__perm_write_is_false { assume((post1_self_.spec_seq)@[6].perm.write == false); }
    if g__post1_self__spec_seq___6__perm_execute_disable_is_true { assume((post1_self_.spec_seq)@[6].perm.execute_disable == true); }
    if g__post1_self__spec_seq___6__perm_execute_disable_is_false { assume((post1_self_.spec_seq)@[6].perm.execute_disable == false); }
    if g__post1_self__spec_seq___6__perm_user_is_true { assume((post1_self_.spec_seq)@[6].perm.user == true); }
    if g__post1_self__spec_seq___6__perm_user_is_false { assume((post1_self_.spec_seq)@[6].perm.user == false); }
    if g__post1_self__spec_seq___7__perm_present_is_true { assume((post1_self_.spec_seq)@[7].perm.present == true); }
    if g__post1_self__spec_seq___7__perm_present_is_false { assume((post1_self_.spec_seq)@[7].perm.present == false); }
    if g__post1_self__spec_seq___7__perm_ps_is_true { assume((post1_self_.spec_seq)@[7].perm.ps == true); }
    if g__post1_self__spec_seq___7__perm_ps_is_false { assume((post1_self_.spec_seq)@[7].perm.ps == false); }
    if g__post1_self__spec_seq___7__perm_write_is_true { assume((post1_self_.spec_seq)@[7].perm.write == true); }
    if g__post1_self__spec_seq___7__perm_write_is_false { assume((post1_self_.spec_seq)@[7].perm.write == false); }
    if g__post1_self__spec_seq___7__perm_execute_disable_is_true { assume((post1_self_.spec_seq)@[7].perm.execute_disable == true); }
    if g__post1_self__spec_seq___7__perm_execute_disable_is_false { assume((post1_self_.spec_seq)@[7].perm.execute_disable == false); }
    if g__post1_self__spec_seq___7__perm_user_is_true { assume((post1_self_.spec_seq)@[7].perm.user == true); }
    if g__post1_self__spec_seq___7__perm_user_is_false { assume((post1_self_.spec_seq)@[7].perm.user == false); }
    if g__post2_self__spec_seq___leneq { assume((post2_self_.spec_seq)@.len() == k__post2_self__spec_seq___leneq); }
    if g__post2_self__spec_seq___lenrng { assume((post2_self_.spec_seq)@.len() >= k__post2_self__spec_seq___lenrng_lo && (post2_self_.spec_seq)@.len() <= k__post2_self__spec_seq___lenrng_hi); }
    if g__post2_self__spec_seq___0__perm_present_is_true { assume((post2_self_.spec_seq)@[0].perm.present == true); }
    if g__post2_self__spec_seq___0__perm_present_is_false { assume((post2_self_.spec_seq)@[0].perm.present == false); }
    if g__post2_self__spec_seq___0__perm_ps_is_true { assume((post2_self_.spec_seq)@[0].perm.ps == true); }
    if g__post2_self__spec_seq___0__perm_ps_is_false { assume((post2_self_.spec_seq)@[0].perm.ps == false); }
    if g__post2_self__spec_seq___0__perm_write_is_true { assume((post2_self_.spec_seq)@[0].perm.write == true); }
    if g__post2_self__spec_seq___0__perm_write_is_false { assume((post2_self_.spec_seq)@[0].perm.write == false); }
    if g__post2_self__spec_seq___0__perm_execute_disable_is_true { assume((post2_self_.spec_seq)@[0].perm.execute_disable == true); }
    if g__post2_self__spec_seq___0__perm_execute_disable_is_false { assume((post2_self_.spec_seq)@[0].perm.execute_disable == false); }
    if g__post2_self__spec_seq___0__perm_user_is_true { assume((post2_self_.spec_seq)@[0].perm.user == true); }
    if g__post2_self__spec_seq___0__perm_user_is_false { assume((post2_self_.spec_seq)@[0].perm.user == false); }
    if g__post2_self__spec_seq___1__perm_present_is_true { assume((post2_self_.spec_seq)@[1].perm.present == true); }
    if g__post2_self__spec_seq___1__perm_present_is_false { assume((post2_self_.spec_seq)@[1].perm.present == false); }
    if g__post2_self__spec_seq___1__perm_ps_is_true { assume((post2_self_.spec_seq)@[1].perm.ps == true); }
    if g__post2_self__spec_seq___1__perm_ps_is_false { assume((post2_self_.spec_seq)@[1].perm.ps == false); }
    if g__post2_self__spec_seq___1__perm_write_is_true { assume((post2_self_.spec_seq)@[1].perm.write == true); }
    if g__post2_self__spec_seq___1__perm_write_is_false { assume((post2_self_.spec_seq)@[1].perm.write == false); }
    if g__post2_self__spec_seq___1__perm_execute_disable_is_true { assume((post2_self_.spec_seq)@[1].perm.execute_disable == true); }
    if g__post2_self__spec_seq___1__perm_execute_disable_is_false { assume((post2_self_.spec_seq)@[1].perm.execute_disable == false); }
    if g__post2_self__spec_seq___1__perm_user_is_true { assume((post2_self_.spec_seq)@[1].perm.user == true); }
    if g__post2_self__spec_seq___1__perm_user_is_false { assume((post2_self_.spec_seq)@[1].perm.user == false); }
    if g__post2_self__spec_seq___2__perm_present_is_true { assume((post2_self_.spec_seq)@[2].perm.present == true); }
    if g__post2_self__spec_seq___2__perm_present_is_false { assume((post2_self_.spec_seq)@[2].perm.present == false); }
    if g__post2_self__spec_seq___2__perm_ps_is_true { assume((post2_self_.spec_seq)@[2].perm.ps == true); }
    if g__post2_self__spec_seq___2__perm_ps_is_false { assume((post2_self_.spec_seq)@[2].perm.ps == false); }
    if g__post2_self__spec_seq___2__perm_write_is_true { assume((post2_self_.spec_seq)@[2].perm.write == true); }
    if g__post2_self__spec_seq___2__perm_write_is_false { assume((post2_self_.spec_seq)@[2].perm.write == false); }
    if g__post2_self__spec_seq___2__perm_execute_disable_is_true { assume((post2_self_.spec_seq)@[2].perm.execute_disable == true); }
    if g__post2_self__spec_seq___2__perm_execute_disable_is_false { assume((post2_self_.spec_seq)@[2].perm.execute_disable == false); }
    if g__post2_self__spec_seq___2__perm_user_is_true { assume((post2_self_.spec_seq)@[2].perm.user == true); }
    if g__post2_self__spec_seq___2__perm_user_is_false { assume((post2_self_.spec_seq)@[2].perm.user == false); }
    if g__post2_self__spec_seq___3__perm_present_is_true { assume((post2_self_.spec_seq)@[3].perm.present == true); }
    if g__post2_self__spec_seq___3__perm_present_is_false { assume((post2_self_.spec_seq)@[3].perm.present == false); }
    if g__post2_self__spec_seq___3__perm_ps_is_true { assume((post2_self_.spec_seq)@[3].perm.ps == true); }
    if g__post2_self__spec_seq___3__perm_ps_is_false { assume((post2_self_.spec_seq)@[3].perm.ps == false); }
    if g__post2_self__spec_seq___3__perm_write_is_true { assume((post2_self_.spec_seq)@[3].perm.write == true); }
    if g__post2_self__spec_seq___3__perm_write_is_false { assume((post2_self_.spec_seq)@[3].perm.write == false); }
    if g__post2_self__spec_seq___3__perm_execute_disable_is_true { assume((post2_self_.spec_seq)@[3].perm.execute_disable == true); }
    if g__post2_self__spec_seq___3__perm_execute_disable_is_false { assume((post2_self_.spec_seq)@[3].perm.execute_disable == false); }
    if g__post2_self__spec_seq___3__perm_user_is_true { assume((post2_self_.spec_seq)@[3].perm.user == true); }
    if g__post2_self__spec_seq___3__perm_user_is_false { assume((post2_self_.spec_seq)@[3].perm.user == false); }
    if g__post2_self__spec_seq___4__perm_present_is_true { assume((post2_self_.spec_seq)@[4].perm.present == true); }
    if g__post2_self__spec_seq___4__perm_present_is_false { assume((post2_self_.spec_seq)@[4].perm.present == false); }
    if g__post2_self__spec_seq___4__perm_ps_is_true { assume((post2_self_.spec_seq)@[4].perm.ps == true); }
    if g__post2_self__spec_seq___4__perm_ps_is_false { assume((post2_self_.spec_seq)@[4].perm.ps == false); }
    if g__post2_self__spec_seq___4__perm_write_is_true { assume((post2_self_.spec_seq)@[4].perm.write == true); }
    if g__post2_self__spec_seq___4__perm_write_is_false { assume((post2_self_.spec_seq)@[4].perm.write == false); }
    if g__post2_self__spec_seq___4__perm_execute_disable_is_true { assume((post2_self_.spec_seq)@[4].perm.execute_disable == true); }
    if g__post2_self__spec_seq___4__perm_execute_disable_is_false { assume((post2_self_.spec_seq)@[4].perm.execute_disable == false); }
    if g__post2_self__spec_seq___4__perm_user_is_true { assume((post2_self_.spec_seq)@[4].perm.user == true); }
    if g__post2_self__spec_seq___4__perm_user_is_false { assume((post2_self_.spec_seq)@[4].perm.user == false); }
    if g__post2_self__spec_seq___5__perm_present_is_true { assume((post2_self_.spec_seq)@[5].perm.present == true); }
    if g__post2_self__spec_seq___5__perm_present_is_false { assume((post2_self_.spec_seq)@[5].perm.present == false); }
    if g__post2_self__spec_seq___5__perm_ps_is_true { assume((post2_self_.spec_seq)@[5].perm.ps == true); }
    if g__post2_self__spec_seq___5__perm_ps_is_false { assume((post2_self_.spec_seq)@[5].perm.ps == false); }
    if g__post2_self__spec_seq___5__perm_write_is_true { assume((post2_self_.spec_seq)@[5].perm.write == true); }
    if g__post2_self__spec_seq___5__perm_write_is_false { assume((post2_self_.spec_seq)@[5].perm.write == false); }
    if g__post2_self__spec_seq___5__perm_execute_disable_is_true { assume((post2_self_.spec_seq)@[5].perm.execute_disable == true); }
    if g__post2_self__spec_seq___5__perm_execute_disable_is_false { assume((post2_self_.spec_seq)@[5].perm.execute_disable == false); }
    if g__post2_self__spec_seq___5__perm_user_is_true { assume((post2_self_.spec_seq)@[5].perm.user == true); }
    if g__post2_self__spec_seq___5__perm_user_is_false { assume((post2_self_.spec_seq)@[5].perm.user == false); }
    if g__post2_self__spec_seq___6__perm_present_is_true { assume((post2_self_.spec_seq)@[6].perm.present == true); }
    if g__post2_self__spec_seq___6__perm_present_is_false { assume((post2_self_.spec_seq)@[6].perm.present == false); }
    if g__post2_self__spec_seq___6__perm_ps_is_true { assume((post2_self_.spec_seq)@[6].perm.ps == true); }
    if g__post2_self__spec_seq___6__perm_ps_is_false { assume((post2_self_.spec_seq)@[6].perm.ps == false); }
    if g__post2_self__spec_seq___6__perm_write_is_true { assume((post2_self_.spec_seq)@[6].perm.write == true); }
    if g__post2_self__spec_seq___6__perm_write_is_false { assume((post2_self_.spec_seq)@[6].perm.write == false); }
    if g__post2_self__spec_seq___6__perm_execute_disable_is_true { assume((post2_self_.spec_seq)@[6].perm.execute_disable == true); }
    if g__post2_self__spec_seq___6__perm_execute_disable_is_false { assume((post2_self_.spec_seq)@[6].perm.execute_disable == false); }
    if g__post2_self__spec_seq___6__perm_user_is_true { assume((post2_self_.spec_seq)@[6].perm.user == true); }
    if g__post2_self__spec_seq___6__perm_user_is_false { assume((post2_self_.spec_seq)@[6].perm.user == false); }
    if g__post2_self__spec_seq___7__perm_present_is_true { assume((post2_self_.spec_seq)@[7].perm.present == true); }
    if g__post2_self__spec_seq___7__perm_present_is_false { assume((post2_self_.spec_seq)@[7].perm.present == false); }
    if g__post2_self__spec_seq___7__perm_ps_is_true { assume((post2_self_.spec_seq)@[7].perm.ps == true); }
    if g__post2_self__spec_seq___7__perm_ps_is_false { assume((post2_self_.spec_seq)@[7].perm.ps == false); }
    if g__post2_self__spec_seq___7__perm_write_is_true { assume((post2_self_.spec_seq)@[7].perm.write == true); }
    if g__post2_self__spec_seq___7__perm_write_is_false { assume((post2_self_.spec_seq)@[7].perm.write == false); }
    if g__post2_self__spec_seq___7__perm_execute_disable_is_true { assume((post2_self_.spec_seq)@[7].perm.execute_disable == true); }
    if g__post2_self__spec_seq___7__perm_execute_disable_is_false { assume((post2_self_.spec_seq)@[7].perm.execute_disable == false); }
    if g__post2_self__spec_seq___7__perm_user_is_true { assume((post2_self_.spec_seq)@[7].perm.user == true); }
    if g__post2_self__spec_seq___7__perm_user_is_false { assume((post2_self_.spec_seq)@[7].perm.user == false); }
    if g_neq_tuple { assume(!det_set_equal(r1, r2, post1_self_, post2_self_)); }
}
// === END INJECTED ===

}
