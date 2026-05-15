use vstd::prelude::*;

fn main() {}


verus! {

type ID = EndPoint;

impl Ordering{

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

    fn set(&mut self, i: usize, k: K)
        requires old(self).valid(),
                 i < old(self)@.len(),
                 i > 0 ==> old(self)@[i as int - 1].cmp_spec(k).lt(),
                 i < old(self)@.len() - 1 ==> k.cmp_spec(old(self)@[i as int + 1]).lt(),
        ensures
            self.valid(),
            self@ == old(self)@.update(i as int, k),
    {
        self.v.set(i, k);

        assert forall |m, n| 0 <= m < n < self@.len() implies #[trigger](self@[m].cmp_spec(self@[n]).lt()) by {
            K::cmp_properties();
        }

        assert forall |i, j| 0 <= i < self@.len() && 0 <= j < self@.len() && i != j implies self@[i] != self@[j] by {
            K::cmp_properties();
        }

    }
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
}

pub enum Ordering {
    Less,
    Equal,
    Greater,
}

pub trait VerusClone : Sized {
}

// === INJECTED DET CHECK ===
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_set_equal<K: KeyTrait + VerusClone>(r1: (), r2: (), post1_self_: StrictlyOrderedVec<K>, post2_self_: StrictlyOrderedVec<K>) -> bool {
    (r1 == r2)
    && (post1_self_ == post2_self_)
}

proof fn det_set<K: KeyTrait + VerusClone>(g_i_eq: bool, k_i_eq: int, g_i_rng: bool, k_i_rng_lo: int, k_i_rng_hi: int, g_neq_tuple: bool, pre_self_: StrictlyOrderedVec<K>, i: usize, k: K, post1_self_: StrictlyOrderedVec<K>, r1: (), post2_self_: StrictlyOrderedVec<K>, r2: ())
    requires (pre_self_.valid()), (i < pre_self_@.len()), (i > 0 ==> pre_self_@[i as int - 1].cmp_spec(k).lt()), (i < pre_self_@.len() - 1 ==> k.cmp_spec(pre_self_@[i as int + 1]).lt()),
    ensures
        ({
            &&& (post1_self_.valid())
            &&& (post1_self_@ == pre_self_@.update(i as int, k))
            &&& (post2_self_.valid())
            &&& (post2_self_@ == pre_self_@.update(i as int, k))
        }) ==> det_set_equal(r1, r2, post1_self_, post2_self_),
{
    if g_i_eq { assume(i as int == k_i_eq); }
    if g_i_rng { assume(i as int >= k_i_rng_lo && i as int <= k_i_rng_hi); }
    if g_neq_tuple { assume(!det_set_equal(r1, r2, post1_self_, post2_self_)); }
}
// === END INJECTED ===

}
