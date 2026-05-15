use vstd::prelude::*;

fn main() {}

verus! {

pub struct AbstractEndPoint {
    pub id: Seq<u8>,
}

impl Ordering {
    pub open spec fn lt(self) -> bool {
        matches!(self, Ordering::Less)
    }
    pub const fn is_lt(self) -> (b:bool)
        ensures b == self.lt(),
    {
        matches!(self, Ordering::Less)
    }

}

struct StrictlyOrderedVec<K: KeyTrait> {
    v: Vec<K>,
}

spec fn sorted<K: KeyTrait>(s: Seq<K>) -> bool
{
    forall |i, j| #![auto] 0 <= i < j < s.len() ==> s[i].cmp_spec(s[j]).lt()
}

impl<K: KeyTrait + VerusClone> StrictlyOrderedVec<K> {

    pub closed spec fn view(self) -> Seq<K> {
        self.v@
    }

    pub closed spec fn valid(self) -> bool {
        sorted(self@) && self@.no_duplicates()
    }
}
#[verifier::reject_recursive_types(K)]

struct StrictlyOrderedMap<K: KeyTrait + VerusClone> {
    keys: StrictlyOrderedVec<K>,
    vals: Vec<ID>,
    m: Ghost<Map<K, ID>>,
}

impl<K: KeyTrait + VerusClone> StrictlyOrderedMap<K> {

    pub closed spec fn view(self) -> Map<K,ID> {
        self.m@
    }

    pub closed spec fn map_valid(self) -> bool
        // recommends self.keys@.len() == self.vals.len()  // error: public function requires cannot refer to private items
    {
        &&& self.m@.dom().finite()
        &&& self.m@.dom() == self.keys@.to_set()
        &&& forall |i| 0 <= i < self.keys@.len() ==> #[trigger] (self.m@[self.keys@.index(i)]) == self.vals@.index(i)
    }

    pub closed spec fn valid(self) -> bool {
        &&& self.keys.valid()
        &&& self.keys@.len() == self.vals.len()
        &&& self.map_valid()
    }

	#[verifier::external_body]
    fn values_agree(&self, lo: usize, hi: usize, v: &ID) -> (ret:(bool, bool))
        requires 
            self.valid(),
            0 <= lo <= hi < self.keys@.len(),
        ensures 
            ret.0 == forall |i| #![auto] lo <= i <= hi ==> self.vals@[i]@ == v@,
            !ret.0 ==> (ret.1 == (self.vals@[hi as int]@ != v@ && forall |i| #![auto] lo <= i < hi ==> self.vals@[i]@ == v@)),
	{
		unimplemented!()
	}

    fn keys_in_index_range_agree(&self, lo: usize, hi: usize, v: &ID) -> (ret:(bool, bool))
        requires 
            self.valid(),
            0 <= lo <= hi < self.keys@.len(),
        ensures 
            ret.0 == forall |i| #![auto] lo <= i <= hi ==> self@[self.keys@[i]]@ == v@,
            !ret.0 ==> (ret.1 == (self@[self.keys@[hi as int]]@ != v@ && (forall |i| #![auto] lo <= i < hi ==> self@[self.keys@[i]]@ == v@))),
    {
        assert(self.valid());
        assert(forall |i| lo <= i <= hi ==> self@[self.keys@[i]] == self.vals@[i]);
        let (agree, almost) = self.values_agree(lo, hi, v);
        
        (agree, almost)
    }
}

#[verifier::reject_recursive_types(K)]

pub struct DelegationMap<K: KeyTrait + VerusClone> {
    // Our efficient implementation based on ranges
    lows: StrictlyOrderedMap<K>,
    // Our spec version
    m: Ghost<Map<K, AbstractEndPoint>>,

}

type ID = EndPoint;

pub struct EndPoint {
    pub id: Vec<u8>,
}

impl EndPoint {
    pub open spec fn view(self) -> AbstractEndPoint {
        AbstractEndPoint{id: self.id@}
    }
}


pub trait KeyTrait : Sized {
    spec fn cmp_spec(self, other: Self) -> Ordering;
}

pub enum Ordering {
    Less,
    Equal,
    Greater,
}

pub trait VerusClone : Sized {}


// === INJECTED DET CHECK ===
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_values_agree_equal(r1: (bool, bool), r2: (bool, bool)) -> bool {
    (r1 == r2)
}

proof fn det_values_agree<K: KeyTrait + VerusClone>(g_lo_eq: bool, k_lo_eq: int, g_lo_rng: bool, k_lo_rng_lo: int, k_lo_rng_hi: int, g_hi_eq: bool, k_hi_eq: int, g_hi_rng: bool, k_hi_rng_lo: int, k_hi_rng_hi: int, g_neq_tuple: bool, self_: StrictlyOrderedMap<K>, lo: usize, hi: usize, v: ID, r1: (bool, bool), r2: (bool, bool))
    requires (self_.valid()), (0 <= lo <= hi < self_.keys@.len()),
    ensures
        ({
            &&& (r1.0 == forall |i| #![auto] lo <= i <= hi ==> self_.vals@[i]@ == v@)
            &&& (!r1.0 ==> (r1.1 == (self_.vals@[hi as int]@ != v@ && forall |i| #![auto] lo <= i < hi ==> self_.vals@[i]@ == v@)))
            &&& (r2.0 == forall |i| #![auto] lo <= i <= hi ==> self_.vals@[i]@ == v@)
            &&& (!r2.0 ==> (r2.1 == (self_.vals@[hi as int]@ != v@ && forall |i| #![auto] lo <= i < hi ==> self_.vals@[i]@ == v@)))
        }) ==> det_values_agree_equal(r1, r2),
{
    if g_lo_eq { assume(lo as int == k_lo_eq); }
    if g_lo_rng { assume(lo as int >= k_lo_rng_lo && lo as int <= k_lo_rng_hi); }
    if g_hi_eq { assume(hi as int == k_hi_eq); }
    if g_hi_rng { assume(hi as int >= k_hi_rng_lo && hi as int <= k_hi_rng_hi); }
    if g_neq_tuple { assume(!det_values_agree_equal(r1, r2)); }
}
// === END INJECTED ===

}
