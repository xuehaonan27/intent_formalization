use vstd::prelude::*;
use vstd::set_lib::*;

fn main() {}

verus! {

type ID = EndPoint;


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
    pub const fn is_lt(self) -> (b:bool)
        ensures b == self.lt(),
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

    fn insert(&mut self, k: K) -> (i: usize)
        requires
            old(self).valid(),
            !old(self)@.contains(k),
        ensures self.valid(),
            self@.len() == old(self)@.len() + 1,
            0 <= i < self@.len(),
            self@ == old(self)@.insert(i as int, k),
            self@.to_set() == old(self)@.to_set().insert(k),
    {
        // Find the index where we should insert k
        let mut index: usize = 0;
        while index < self.v.len() && self.v[index].cmp(&k).is_lt()
            invariant
                0 <= index <= self@.len(),
                forall |i| 0 <= i < index ==> (#[trigger] self@.index(i).cmp_spec(k)).lt()
            decreases
               self@.len() - index
        {
            index = index + 1;
        }
        self.v.insert(index, k);
        assert forall |m, n| 0 <= m < n < self@.len() implies #[trigger](self@[m].cmp_spec(self@[n]).lt()) by {
            K::cmp_properties();
        }
        assert(self@.to_set() == old(self)@.to_set().insert(k)) by {
            let new_s = self@.to_set();
            let old_s = old(self)@.to_set().insert(k);
            assert(self@[index as int] == k);   // OBSERVE
            assert forall |e| old_s.contains(e) implies new_s.contains(e) by {
                if e == k {
                } else {
                    let i = choose |i: int| 0 <= i < old(self)@.len() && old(self)@[i] == e;
                    if i < index {
                        assert(self@[i] == e);      // OBSERVE
                    } else {
                        assert(self@[i+1] == e);    // OBSERVE
                    }
                }
            };
            assert_sets_equal!(new_s, old_s);
        };
        return index;
    }
}
#[verifier::reject_recursive_types(K)]

struct StrictlyOrderedMap<K: KeyTrait + VerusClone> {
    keys: StrictlyOrderedVec<K>,
    vals: Vec<ID>,
    m: Ghost<Map<K, ID>>,
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
        requires 
            true,
        ensures 
            o == self.cmp_spec(*other);
}

pub enum Ordering {
    Less,
    Equal,
    Greater,
}

pub trait VerusClone : Sized {
    fn clone(&self) -> (o: Self)
        ensures o == self;  // this is way too restrictive; it kind of demands Copy. But we don't have a View trait yet. :v(
}



// === INJECTED DET CHECK ===
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_insert_equal(r1: usize, r2: usize, post1_self_: Self, post2_self_: Self) -> bool {
    (r1 == r2)
    && (post1_self_ == post2_self_)
}

proof fn det_insert(g_r1_eq: bool, k_r1_eq: int, g_r1_rng: bool, k_r1_rng_lo: int, k_r1_rng_hi: int, g_r2_eq: bool, k_r2_eq: int, g_r2_rng: bool, k_r2_rng_lo: int, k_r2_rng_hi: int, g_neq_tuple: bool, pre_self_: Self, k: K, post1_self_: Self, r1: usize, post2_self_: Self, r2: usize)
    requires (pre_self_.valid()), (!pre_self_@.contains(k)),
    ensures
        ({
            &&& (post1_self_.valid())
            &&& (post1_self_@.len() == pre_self_@.len() + 1)
            &&& (0 <= r1 < post1_self_@.len())
            &&& (post1_self_@ == pre_self_@.insert(r1 as int, k))
            &&& (post1_self_@.to_set() == pre_self_@.to_set().insert(k))
            &&& (post2_self_.valid())
            &&& (post2_self_@.len() == pre_self_@.len() + 1)
            &&& (0 <= r2 < post2_self_@.len())
            &&& (post2_self_@ == pre_self_@.insert(r2 as int, k))
            &&& (post2_self_@.to_set() == pre_self_@.to_set().insert(k))
        }) ==> det_insert_equal(r1, r2, post1_self_, post2_self_),
{
    if g_r1_eq { assume(r1 as int == k_r1_eq); }
    if g_r1_rng { assume(r1 as int >= k_r1_rng_lo && r1 as int <= k_r1_rng_hi); }
    if g_r2_eq { assume(r2 as int == k_r2_eq); }
    if g_r2_rng { assume(r2 as int >= k_r2_rng_lo && r2 as int <= k_r2_rng_hi); }
    if g_neq_tuple { assume(!det_insert_equal(r1, r2, post1_self_, post2_self_)); }
}
// === END INJECTED ===

}
