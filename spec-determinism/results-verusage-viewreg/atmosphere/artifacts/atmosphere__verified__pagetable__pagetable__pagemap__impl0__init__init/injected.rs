use vstd::prelude::*;

fn main() {}

verus!{

pub type PAddr = usize;

// File: util/page_ptr_util_u.rs
//
pub open spec fn MEM_valid(v: PAddr) -> bool {
    v & (!MEM_MASK) as usize == 0
}

// File: pagetable/pagemap.rs
pub struct PageMap {
    pub ar: Array<usize, 512>,
    pub spec_seq: Ghost<Seq<PageEntry>>,  // pub level: Ghost<usize>,
    // not used for now.
}

impl PageMap {

    pub fn init(&mut self)
        requires
            old(self).ar.wf(),
            old(self).spec_seq@.len() == 512,
        ensures
            self.wf(),
            forall|i: int| #![trigger self@[i].is_empty()] 0 <= i < 512 ==> self@[i].is_empty(),
    {
        for i in 0..512
            invariant
                0 <= i <= 512,
                self.ar.wf(),
                self.spec_seq@.len() == 512,
                forall|j: int|
                    #![trigger usize2page_entry(self.ar@[j])]
                    0 <= j < i ==> (usize2page_entry(self.ar@[j]) =~= self.spec_seq@[j]),
                forall|j: int|
                    #![trigger self.ar@[j]]
                    0 <= j < i ==> (usize2page_entry(self.ar@[j]).is_empty() <==> self.ar@[j] == 0),
                forall|j: int|
                    #![trigger self.ar@[j]]
                    0 <= j < i ==> usize2page_entry(self.ar@[j]).is_empty(),
                forall|j: int| #![trigger self@[j].is_empty()] 0 <= j < i ==> self@[j].is_empty(),
        {
            let ghost_view = Ghost(self@);
            self.ar.set(i, 0usize);
            assert(self@ == ghost_view);
            proof {
                zero_leads_is_empty_page_entry();
                assert(usize2page_entry(0usize).is_empty());
                self.spec_seq@ = self.spec_seq@.update(i as int, usize2page_entry(0usize));
            }
        }
    }


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
spec fn det_init_equal(r1: (), r2: (), post1_self_: PageMap, post2_self_: PageMap) -> bool {
    (r1 == r2)
    && (((post1_self_).view() == (post2_self_).view()))
}

proof fn det_init(g__pre_self__spec_seq___leneq: bool, k__pre_self__spec_seq___leneq: nat, g__pre_self__spec_seq___lenrng: bool, k__pre_self__spec_seq___lenrng_lo: nat, k__pre_self__spec_seq___lenrng_hi: nat, g__pre_self__spec_seq___0__perm_present_is_true: bool, g__pre_self__spec_seq___0__perm_present_is_false: bool, g__pre_self__spec_seq___0__perm_ps_is_true: bool, g__pre_self__spec_seq___0__perm_ps_is_false: bool, g__pre_self__spec_seq___0__perm_write_is_true: bool, g__pre_self__spec_seq___0__perm_write_is_false: bool, g__pre_self__spec_seq___0__perm_execute_disable_is_true: bool, g__pre_self__spec_seq___0__perm_execute_disable_is_false: bool, g__pre_self__spec_seq___0__perm_user_is_true: bool, g__pre_self__spec_seq___0__perm_user_is_false: bool, g__pre_self__spec_seq___1__perm_present_is_true: bool, g__pre_self__spec_seq___1__perm_present_is_false: bool, g__pre_self__spec_seq___1__perm_ps_is_true: bool, g__pre_self__spec_seq___1__perm_ps_is_false: bool, g__pre_self__spec_seq___1__perm_write_is_true: bool, g__pre_self__spec_seq___1__perm_write_is_false: bool, g__pre_self__spec_seq___1__perm_execute_disable_is_true: bool, g__pre_self__spec_seq___1__perm_execute_disable_is_false: bool, g__pre_self__spec_seq___1__perm_user_is_true: bool, g__pre_self__spec_seq___1__perm_user_is_false: bool, g__pre_self__spec_seq___2__perm_present_is_true: bool, g__pre_self__spec_seq___2__perm_present_is_false: bool, g__pre_self__spec_seq___2__perm_ps_is_true: bool, g__pre_self__spec_seq___2__perm_ps_is_false: bool, g__pre_self__spec_seq___2__perm_write_is_true: bool, g__pre_self__spec_seq___2__perm_write_is_false: bool, g__pre_self__spec_seq___2__perm_execute_disable_is_true: bool, g__pre_self__spec_seq___2__perm_execute_disable_is_false: bool, g__pre_self__spec_seq___2__perm_user_is_true: bool, g__pre_self__spec_seq___2__perm_user_is_false: bool, g__pre_self__spec_seq___3__perm_present_is_true: bool, g__pre_self__spec_seq___3__perm_present_is_false: bool, g__pre_self__spec_seq___3__perm_ps_is_true: bool, g__pre_self__spec_seq___3__perm_ps_is_false: bool, g__pre_self__spec_seq___3__perm_write_is_true: bool, g__pre_self__spec_seq___3__perm_write_is_false: bool, g__pre_self__spec_seq___3__perm_execute_disable_is_true: bool, g__pre_self__spec_seq___3__perm_execute_disable_is_false: bool, g__pre_self__spec_seq___3__perm_user_is_true: bool, g__pre_self__spec_seq___3__perm_user_is_false: bool, g__pre_self__spec_seq___4__perm_present_is_true: bool, g__pre_self__spec_seq___4__perm_present_is_false: bool, g__pre_self__spec_seq___4__perm_ps_is_true: bool, g__pre_self__spec_seq___4__perm_ps_is_false: bool, g__pre_self__spec_seq___4__perm_write_is_true: bool, g__pre_self__spec_seq___4__perm_write_is_false: bool, g__pre_self__spec_seq___4__perm_execute_disable_is_true: bool, g__pre_self__spec_seq___4__perm_execute_disable_is_false: bool, g__pre_self__spec_seq___4__perm_user_is_true: bool, g__pre_self__spec_seq___4__perm_user_is_false: bool, g__pre_self__spec_seq___5__perm_present_is_true: bool, g__pre_self__spec_seq___5__perm_present_is_false: bool, g__pre_self__spec_seq___5__perm_ps_is_true: bool, g__pre_self__spec_seq___5__perm_ps_is_false: bool, g__pre_self__spec_seq___5__perm_write_is_true: bool, g__pre_self__spec_seq___5__perm_write_is_false: bool, g__pre_self__spec_seq___5__perm_execute_disable_is_true: bool, g__pre_self__spec_seq___5__perm_execute_disable_is_false: bool, g__pre_self__spec_seq___5__perm_user_is_true: bool, g__pre_self__spec_seq___5__perm_user_is_false: bool, g__pre_self__spec_seq___6__perm_present_is_true: bool, g__pre_self__spec_seq___6__perm_present_is_false: bool, g__pre_self__spec_seq___6__perm_ps_is_true: bool, g__pre_self__spec_seq___6__perm_ps_is_false: bool, g__pre_self__spec_seq___6__perm_write_is_true: bool, g__pre_self__spec_seq___6__perm_write_is_false: bool, g__pre_self__spec_seq___6__perm_execute_disable_is_true: bool, g__pre_self__spec_seq___6__perm_execute_disable_is_false: bool, g__pre_self__spec_seq___6__perm_user_is_true: bool, g__pre_self__spec_seq___6__perm_user_is_false: bool, g__pre_self__spec_seq___7__perm_present_is_true: bool, g__pre_self__spec_seq___7__perm_present_is_false: bool, g__pre_self__spec_seq___7__perm_ps_is_true: bool, g__pre_self__spec_seq___7__perm_ps_is_false: bool, g__pre_self__spec_seq___7__perm_write_is_true: bool, g__pre_self__spec_seq___7__perm_write_is_false: bool, g__pre_self__spec_seq___7__perm_execute_disable_is_true: bool, g__pre_self__spec_seq___7__perm_execute_disable_is_false: bool, g__pre_self__spec_seq___7__perm_user_is_true: bool, g__pre_self__spec_seq___7__perm_user_is_false: bool, g__post1_self__spec_seq___leneq: bool, k__post1_self__spec_seq___leneq: nat, g__post1_self__spec_seq___lenrng: bool, k__post1_self__spec_seq___lenrng_lo: nat, k__post1_self__spec_seq___lenrng_hi: nat, g__post1_self__spec_seq___0__perm_present_is_true: bool, g__post1_self__spec_seq___0__perm_present_is_false: bool, g__post1_self__spec_seq___0__perm_ps_is_true: bool, g__post1_self__spec_seq___0__perm_ps_is_false: bool, g__post1_self__spec_seq___0__perm_write_is_true: bool, g__post1_self__spec_seq___0__perm_write_is_false: bool, g__post1_self__spec_seq___0__perm_execute_disable_is_true: bool, g__post1_self__spec_seq___0__perm_execute_disable_is_false: bool, g__post1_self__spec_seq___0__perm_user_is_true: bool, g__post1_self__spec_seq___0__perm_user_is_false: bool, g__post1_self__spec_seq___1__perm_present_is_true: bool, g__post1_self__spec_seq___1__perm_present_is_false: bool, g__post1_self__spec_seq___1__perm_ps_is_true: bool, g__post1_self__spec_seq___1__perm_ps_is_false: bool, g__post1_self__spec_seq___1__perm_write_is_true: bool, g__post1_self__spec_seq___1__perm_write_is_false: bool, g__post1_self__spec_seq___1__perm_execute_disable_is_true: bool, g__post1_self__spec_seq___1__perm_execute_disable_is_false: bool, g__post1_self__spec_seq___1__perm_user_is_true: bool, g__post1_self__spec_seq___1__perm_user_is_false: bool, g__post1_self__spec_seq___2__perm_present_is_true: bool, g__post1_self__spec_seq___2__perm_present_is_false: bool, g__post1_self__spec_seq___2__perm_ps_is_true: bool, g__post1_self__spec_seq___2__perm_ps_is_false: bool, g__post1_self__spec_seq___2__perm_write_is_true: bool, g__post1_self__spec_seq___2__perm_write_is_false: bool, g__post1_self__spec_seq___2__perm_execute_disable_is_true: bool, g__post1_self__spec_seq___2__perm_execute_disable_is_false: bool, g__post1_self__spec_seq___2__perm_user_is_true: bool, g__post1_self__spec_seq___2__perm_user_is_false: bool, g__post1_self__spec_seq___3__perm_present_is_true: bool, g__post1_self__spec_seq___3__perm_present_is_false: bool, g__post1_self__spec_seq___3__perm_ps_is_true: bool, g__post1_self__spec_seq___3__perm_ps_is_false: bool, g__post1_self__spec_seq___3__perm_write_is_true: bool, g__post1_self__spec_seq___3__perm_write_is_false: bool, g__post1_self__spec_seq___3__perm_execute_disable_is_true: bool, g__post1_self__spec_seq___3__perm_execute_disable_is_false: bool, g__post1_self__spec_seq___3__perm_user_is_true: bool, g__post1_self__spec_seq___3__perm_user_is_false: bool, g__post1_self__spec_seq___4__perm_present_is_true: bool, g__post1_self__spec_seq___4__perm_present_is_false: bool, g__post1_self__spec_seq___4__perm_ps_is_true: bool, g__post1_self__spec_seq___4__perm_ps_is_false: bool, g__post1_self__spec_seq___4__perm_write_is_true: bool, g__post1_self__spec_seq___4__perm_write_is_false: bool, g__post1_self__spec_seq___4__perm_execute_disable_is_true: bool, g__post1_self__spec_seq___4__perm_execute_disable_is_false: bool, g__post1_self__spec_seq___4__perm_user_is_true: bool, g__post1_self__spec_seq___4__perm_user_is_false: bool, g__post1_self__spec_seq___5__perm_present_is_true: bool, g__post1_self__spec_seq___5__perm_present_is_false: bool, g__post1_self__spec_seq___5__perm_ps_is_true: bool, g__post1_self__spec_seq___5__perm_ps_is_false: bool, g__post1_self__spec_seq___5__perm_write_is_true: bool, g__post1_self__spec_seq___5__perm_write_is_false: bool, g__post1_self__spec_seq___5__perm_execute_disable_is_true: bool, g__post1_self__spec_seq___5__perm_execute_disable_is_false: bool, g__post1_self__spec_seq___5__perm_user_is_true: bool, g__post1_self__spec_seq___5__perm_user_is_false: bool, g__post1_self__spec_seq___6__perm_present_is_true: bool, g__post1_self__spec_seq___6__perm_present_is_false: bool, g__post1_self__spec_seq___6__perm_ps_is_true: bool, g__post1_self__spec_seq___6__perm_ps_is_false: bool, g__post1_self__spec_seq___6__perm_write_is_true: bool, g__post1_self__spec_seq___6__perm_write_is_false: bool, g__post1_self__spec_seq___6__perm_execute_disable_is_true: bool, g__post1_self__spec_seq___6__perm_execute_disable_is_false: bool, g__post1_self__spec_seq___6__perm_user_is_true: bool, g__post1_self__spec_seq___6__perm_user_is_false: bool, g__post1_self__spec_seq___7__perm_present_is_true: bool, g__post1_self__spec_seq___7__perm_present_is_false: bool, g__post1_self__spec_seq___7__perm_ps_is_true: bool, g__post1_self__spec_seq___7__perm_ps_is_false: bool, g__post1_self__spec_seq___7__perm_write_is_true: bool, g__post1_self__spec_seq___7__perm_write_is_false: bool, g__post1_self__spec_seq___7__perm_execute_disable_is_true: bool, g__post1_self__spec_seq___7__perm_execute_disable_is_false: bool, g__post1_self__spec_seq___7__perm_user_is_true: bool, g__post1_self__spec_seq___7__perm_user_is_false: bool, g__post2_self__spec_seq___leneq: bool, k__post2_self__spec_seq___leneq: nat, g__post2_self__spec_seq___lenrng: bool, k__post2_self__spec_seq___lenrng_lo: nat, k__post2_self__spec_seq___lenrng_hi: nat, g__post2_self__spec_seq___0__perm_present_is_true: bool, g__post2_self__spec_seq___0__perm_present_is_false: bool, g__post2_self__spec_seq___0__perm_ps_is_true: bool, g__post2_self__spec_seq___0__perm_ps_is_false: bool, g__post2_self__spec_seq___0__perm_write_is_true: bool, g__post2_self__spec_seq___0__perm_write_is_false: bool, g__post2_self__spec_seq___0__perm_execute_disable_is_true: bool, g__post2_self__spec_seq___0__perm_execute_disable_is_false: bool, g__post2_self__spec_seq___0__perm_user_is_true: bool, g__post2_self__spec_seq___0__perm_user_is_false: bool, g__post2_self__spec_seq___1__perm_present_is_true: bool, g__post2_self__spec_seq___1__perm_present_is_false: bool, g__post2_self__spec_seq___1__perm_ps_is_true: bool, g__post2_self__spec_seq___1__perm_ps_is_false: bool, g__post2_self__spec_seq___1__perm_write_is_true: bool, g__post2_self__spec_seq___1__perm_write_is_false: bool, g__post2_self__spec_seq___1__perm_execute_disable_is_true: bool, g__post2_self__spec_seq___1__perm_execute_disable_is_false: bool, g__post2_self__spec_seq___1__perm_user_is_true: bool, g__post2_self__spec_seq___1__perm_user_is_false: bool, g__post2_self__spec_seq___2__perm_present_is_true: bool, g__post2_self__spec_seq___2__perm_present_is_false: bool, g__post2_self__spec_seq___2__perm_ps_is_true: bool, g__post2_self__spec_seq___2__perm_ps_is_false: bool, g__post2_self__spec_seq___2__perm_write_is_true: bool, g__post2_self__spec_seq___2__perm_write_is_false: bool, g__post2_self__spec_seq___2__perm_execute_disable_is_true: bool, g__post2_self__spec_seq___2__perm_execute_disable_is_false: bool, g__post2_self__spec_seq___2__perm_user_is_true: bool, g__post2_self__spec_seq___2__perm_user_is_false: bool, g__post2_self__spec_seq___3__perm_present_is_true: bool, g__post2_self__spec_seq___3__perm_present_is_false: bool, g__post2_self__spec_seq___3__perm_ps_is_true: bool, g__post2_self__spec_seq___3__perm_ps_is_false: bool, g__post2_self__spec_seq___3__perm_write_is_true: bool, g__post2_self__spec_seq___3__perm_write_is_false: bool, g__post2_self__spec_seq___3__perm_execute_disable_is_true: bool, g__post2_self__spec_seq___3__perm_execute_disable_is_false: bool, g__post2_self__spec_seq___3__perm_user_is_true: bool, g__post2_self__spec_seq___3__perm_user_is_false: bool, g__post2_self__spec_seq___4__perm_present_is_true: bool, g__post2_self__spec_seq___4__perm_present_is_false: bool, g__post2_self__spec_seq___4__perm_ps_is_true: bool, g__post2_self__spec_seq___4__perm_ps_is_false: bool, g__post2_self__spec_seq___4__perm_write_is_true: bool, g__post2_self__spec_seq___4__perm_write_is_false: bool, g__post2_self__spec_seq___4__perm_execute_disable_is_true: bool, g__post2_self__spec_seq___4__perm_execute_disable_is_false: bool, g__post2_self__spec_seq___4__perm_user_is_true: bool, g__post2_self__spec_seq___4__perm_user_is_false: bool, g__post2_self__spec_seq___5__perm_present_is_true: bool, g__post2_self__spec_seq___5__perm_present_is_false: bool, g__post2_self__spec_seq___5__perm_ps_is_true: bool, g__post2_self__spec_seq___5__perm_ps_is_false: bool, g__post2_self__spec_seq___5__perm_write_is_true: bool, g__post2_self__spec_seq___5__perm_write_is_false: bool, g__post2_self__spec_seq___5__perm_execute_disable_is_true: bool, g__post2_self__spec_seq___5__perm_execute_disable_is_false: bool, g__post2_self__spec_seq___5__perm_user_is_true: bool, g__post2_self__spec_seq___5__perm_user_is_false: bool, g__post2_self__spec_seq___6__perm_present_is_true: bool, g__post2_self__spec_seq___6__perm_present_is_false: bool, g__post2_self__spec_seq___6__perm_ps_is_true: bool, g__post2_self__spec_seq___6__perm_ps_is_false: bool, g__post2_self__spec_seq___6__perm_write_is_true: bool, g__post2_self__spec_seq___6__perm_write_is_false: bool, g__post2_self__spec_seq___6__perm_execute_disable_is_true: bool, g__post2_self__spec_seq___6__perm_execute_disable_is_false: bool, g__post2_self__spec_seq___6__perm_user_is_true: bool, g__post2_self__spec_seq___6__perm_user_is_false: bool, g__post2_self__spec_seq___7__perm_present_is_true: bool, g__post2_self__spec_seq___7__perm_present_is_false: bool, g__post2_self__spec_seq___7__perm_ps_is_true: bool, g__post2_self__spec_seq___7__perm_ps_is_false: bool, g__post2_self__spec_seq___7__perm_write_is_true: bool, g__post2_self__spec_seq___7__perm_write_is_false: bool, g__post2_self__spec_seq___7__perm_execute_disable_is_true: bool, g__post2_self__spec_seq___7__perm_execute_disable_is_false: bool, g__post2_self__spec_seq___7__perm_user_is_true: bool, g__post2_self__spec_seq___7__perm_user_is_false: bool, g_neq_tuple: bool, pre_self_: PageMap, post1_self_: PageMap, r1: (), post2_self_: PageMap, r2: ())
    requires (pre_self_.ar.wf()), (pre_self_.spec_seq@.len() == 512),
    ensures
        ({
            &&& (post1_self_.wf())
            &&& (forall|i: int| #![trigger post1_self_@[i].is_empty()] 0 <= i < 512 ==> post1_self_@[i].is_empty())
            &&& (post2_self_.wf())
            &&& (forall|i: int| #![trigger post2_self_@[i].is_empty()] 0 <= i < 512 ==> post2_self_@[i].is_empty())
        }) ==> det_init_equal(r1, r2, post1_self_, post2_self_),
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
    if g_neq_tuple { assume(!det_init_equal(r1, r2, post1_self_, post2_self_)); }
}
// === END INJECTED ===

}
