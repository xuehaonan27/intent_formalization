#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::std_specs::core::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_index_set_equal<T, Idx, E>(r1: (), r2: (), post1_container: T, post2_container: T) -> bool
    where T: ?Sized + core::ops::IndexMut<Idx> + core::ops::Index<Idx, Output = E> + IndexSetTrustedSpec<
        Idx,
    > {
    (r1 == r2)
    && (post1_container == post2_container)
}

proof fn det_index_set<T, Idx, E>(g_neq_tuple: bool, pre_container: T, index: Idx, val: E, post1_container: T, r1: (), post2_container: T, r2: ())
    where T: ?Sized + core::ops::IndexMut<Idx> + core::ops::Index<Idx, Output = E> + IndexSetTrustedSpec<
        Idx,
    >
    requires (pre_container.spec_index_set_requires(index)),
    ensures
        ({
            &&& (pre_container.spec_index_set_ensures(post1_container, index, val))
            &&& (pre_container.spec_index_set_ensures(post2_container, index, val))
        }) ==> det_index_set_equal::<T, Idx, E>(r1, r2, post1_container, post2_container),
{
    if g_neq_tuple { assume(!det_index_set_equal::<T, Idx, E>(r1, r2, post1_container, post2_container)); }
}
}

fn main() {}
