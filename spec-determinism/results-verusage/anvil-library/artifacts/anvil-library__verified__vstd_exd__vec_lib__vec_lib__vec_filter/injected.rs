use vstd::prelude::*;
use vstd::seq_lib::*;

fn main() {}

verus! {

trait VerusClone: View + Sized {
    fn verus_clone(&self) -> (r: Self)
        ensures self == r;
}

fn vec_filter<V: VerusClone + View + Sized>(v: Vec<V>, f: impl Fn(&V)->bool, f_spec: spec_fn(V)->bool) -> (r: Vec<V>)
    requires
        forall|v: V| #[trigger] f.requires((&v,)),
        forall |v:V,r:bool| f.ensures((&v,), r) ==> f_spec(v) == r,
    ensures r@.to_multiset() =~= v@.to_multiset().filter(f_spec)
{
    let mut r = Vec::new();
    let mut i = 0;
    broadcast use group_seq_properties;
    for i in 0..v.len()
        invariant
            forall|v: V| #[trigger] f.requires((&v,)),
            i <= v.len(),
            r@.to_multiset() =~= v@.subrange(0, i as int).to_multiset().filter(f_spec),
            forall |v:V,r:bool| f.ensures((&v,), r) ==> f_spec(v) == r,
    {
        // This deprecated lemma_seq_properties cannot be replaced by
        // broadcast use group_seq_properties;
        proof { lemma_seq_properties::<V>(); }
        let ghost pre_r = r@.to_multiset();
        assert(
            v@.subrange(0, i as int + 1)
            =~=
            v@.subrange(0, i as int).push(v@[i as int]));
        if f(&v[i]) {
            r.push(v[i].verus_clone());
        }
    }
    r
}


// === INJECTED DET CHECK ===
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_vec_filter_equal(r1: Vec<V>, r2: Vec<V>) -> bool {
    (r1 == r2)
}

proof fn det_vec_filter(g_neq_tuple: bool, v: Vec<V>, f: impl Fn(&V)->bool, f_spec: spec_fn(V)->bool, r1: Vec<V>, r2: Vec<V>)
    requires (forall|v: V| #[trigger] f.requires((&v,))), (forall |v:V,r:bool| f.ensures((&v,), r) ==> f_spec(v) == r),
    ensures
        ({
            &&& (r1@.to_multiset() =~= v@.to_multiset().filter(f_spec))
            &&& (r2@.to_multiset() =~= v@.to_multiset().filter(f_spec))
        }) ==> det_vec_filter_equal(r1, r2),
{
    if g_neq_tuple { assume(!det_vec_filter_equal(r1, r2)); }
}
// === END INJECTED ===

}
