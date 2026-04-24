use vstd::prelude::*;

fn main() {}

verus! {

pub struct AbstractEndPoint {
    pub id: Seq<u8>,
}

impl Ordering {

    pub open spec fn eq(self) -> bool {
        matches!(self, Ordering::Equal)
    }

    pub open spec fn ne(self) -> bool {
        !matches!(self, Ordering::Equal)
    }

    pub open spec fn lt(self) -> bool {
        matches!(self, Ordering::Less)
    }

    pub open spec fn gt(self) -> bool {
        matches!(self, Ordering::Greater)
    }

    pub open spec fn le(self) -> bool {
        !matches!(self, Ordering::Greater)
    }

	#[verifier::external_body]
    pub fn is_eq(self) -> (b:bool)
        ensures b == self.eq(),
	{
		unimplemented!()
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
    fn len(&self) -> (len: usize )
        ensures len == self@.len()
	{
		unimplemented!()
	}

	#[verifier::external_body]
    fn index(&self, i: usize) -> (k: K)
        requires i < self@.len(),
        ensures k == self@[i as int]
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

    fn find_key(&self, k: &K) -> (o: Option<usize>)
        requires self.valid(),
        ensures
            match o {
                None => !self@.contains_key(*k),
                Some(i) => 0 <= i < self.keys@.len() && self.keys@[i as int] == k,
            },
    {
        let mut i = 0;
        while i < self.keys.len()
            invariant forall |j| 0 <= j < i ==> self.keys@[j] != k,
            decreases self.keys@.len() - i
        {
            //println!("Loop {} of find_key", i);
            if self.keys.index(i).cmp(&k).is_eq() {
                proof {
                    K::cmp_properties();
                }
                return Some(i);
            } else {
                proof {
                    K::cmp_properties();
                }
            }
            i = i + 1;
        }
        return None;
    }
}

#[verifier::reject_recursive_types(K)]
pub struct DelegationMap<K: KeyTrait + VerusClone> {
    // Our efficient implementation based on ranges
    lows: StrictlyOrderedMap<K>,
    // Our spec version
    m: Ghost<Map<K, AbstractEndPoint>>,

}


pub struct EndPoint {
    pub id: Vec<u8>,
}

type ID = EndPoint;


pub trait KeyTrait : Sized {

    spec fn cmp_spec(self, other: Self) -> Ordering;

    proof fn cmp_properties()
        ensures
        // Equality is eq  --- TODO: Without this we need to redefine Seq, Set, etc. operators that use ==
        forall |a:Self, b:Self| #![auto] a == b <==> a.cmp_spec(b).eq(),
        // Reflexivity of equality
        forall |a:Self| #![auto] a.cmp_spec(a).eq(),
        // Commutativity of equality
        forall |a:Self, b:Self| (#[trigger] a.cmp_spec(b)).eq() == b.cmp_spec(a).eq(),
        // Transitivity of equality
        forall |a:Self, b:Self, c:Self|
            #[trigger] a.cmp_spec(b).eq() && #[trigger] b.cmp_spec(c).eq() ==> a.cmp_spec(c).eq(),
        // Inequality is asymmetric
        forall |a:Self, b:Self|
            #[trigger] a.cmp_spec(b).lt() <==> b.cmp_spec(a).gt(),
        // Connected
        forall |a:Self, b:Self|
            #![auto] a.cmp_spec(b).ne() ==> a.cmp_spec(b).lt() || b.cmp_spec(a).lt(),
        // Transitivity of inequality
        forall |a:Self, b:Self, c:Self|
            #[trigger] a.cmp_spec(b).lt() && #[trigger] b.cmp_spec(c).lt() ==> a.cmp_spec(c).lt(),
        forall |a:Self, b:Self, c:Self|
            #[trigger] a.cmp_spec(b).lt() && #[trigger] b.cmp_spec(c).le() ==> a.cmp_spec(c).lt(),
        forall |a:Self, b:Self, c:Self|
            #[trigger] a.cmp_spec(b).le() && #[trigger] b.cmp_spec(c).lt() ==> a.cmp_spec(c).lt();

    fn cmp(&self, other: &Self) -> (o: Ordering)
        requires true,
        ensures o == self.cmp_spec(*other);
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
spec fn det_find_key_equal(r1: Option<usize>, r2: Option<usize>) -> bool {
    (((r1 is Some) == (r2 is Some)) && ((r1 is Some) ==> (r1->Some_0 == r2->Some_0)))
}

proof fn det_find_key(g_r1_is_Some: bool, g_r1__Some_0_eq: bool, k_r1__Some_0_eq: int, g_r1__Some_0_rng: bool, k_r1__Some_0_rng_lo: int, k_r1__Some_0_rng_hi: int, g_r1_is_None: bool, g_r2_is_Some: bool, g_r2__Some_0_eq: bool, k_r2__Some_0_eq: int, g_r2__Some_0_rng: bool, k_r2__Some_0_rng_lo: int, k_r2__Some_0_rng_hi: int, g_r2_is_None: bool, g_neq_tuple: bool, self_: Self, k: K, r1: Option<usize>, r2: Option<usize>)
    requires (self_.valid()),
    ensures
        ({
            &&& (match r1 {
                None => !self_@.contains_key(k),
                Some(i) => 0 <= i < self_.keys@.len() && self_.keys@[i as int] == k,
            })
            &&& (match r2 {
                None => !self_@.contains_key(k),
                Some(i) => 0 <= i < self_.keys@.len() && self_.keys@[i as int] == k,
            })
        }) ==> det_find_key_equal(r1, r2),
{
    if g_r1_is_Some { assume(r1 is Some); }
    if g_r1__Some_0_eq { assume(r1 is Some); assume(r1->Some_0 as int == k_r1__Some_0_eq); }
    if g_r1__Some_0_rng { assume(r1 is Some); assume(r1->Some_0 as int >= k_r1__Some_0_rng_lo && r1->Some_0 as int <= k_r1__Some_0_rng_hi); }
    if g_r1_is_None { assume(r1 is None); }
    if g_r2_is_Some { assume(r2 is Some); }
    if g_r2__Some_0_eq { assume(r2 is Some); assume(r2->Some_0 as int == k_r2__Some_0_eq); }
    if g_r2__Some_0_rng { assume(r2 is Some); assume(r2->Some_0 as int >= k_r2__Some_0_rng_lo && r2->Some_0 as int <= k_r2__Some_0_rng_hi); }
    if g_r2_is_None { assume(r2 is None); }
    if g_neq_tuple { assume(!det_find_key_equal(r1, r2)); }
}
// === END INJECTED ===

}
