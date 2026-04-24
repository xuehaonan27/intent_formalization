use vstd::prelude::*;
use vstd::set_lib::*;

fn main(){}

verus! {

impl Ordering {

    pub open spec fn lt(self) -> bool {
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

	#[verifier::external_body]
    fn new() -> (v: Self)
        ensures v@ == Seq::<K>::empty(),
                v.valid(),
	{
		unimplemented!()
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

    fn new() -> (s: Self)
        ensures
            s.valid(),
            s@ == Map::<K,ID>::empty(),
    {
        let keys = StrictlyOrderedVec::new();
        let m = Ghost(Map::empty());
        proof {
            assert_sets_equal!(m@.dom(), keys@.to_set());
        }
        StrictlyOrderedMap {
            keys,
            vals: Vec::new(),
            m,
        }
    }
}

type ID = EndPoint;

pub struct EndPoint {
    pub id: Vec<u8>,
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
spec fn det_new_equal(r1: Self, r2: Self) -> bool {
    (r1 == r2)
}

proof fn det_new(g_neq_tuple: bool, r1: Self, r2: Self)
    ensures
        ({
            &&& (r1@ == Seq::<K>::empty())
            &&& (r1.valid())
            &&& (r2@ == Seq::<K>::empty())
            &&& (r2.valid())
        }) ==> det_new_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_new_equal(r1, r2)); }
}
// === END INJECTED ===

}
