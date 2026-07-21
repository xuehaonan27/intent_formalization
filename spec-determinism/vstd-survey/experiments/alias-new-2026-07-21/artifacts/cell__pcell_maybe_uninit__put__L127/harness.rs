#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::cell::pcell_maybe_uninit::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_put_equal<V>(r1: (), r2: (), post1_perm: PointsTo<V>, post2_perm: PointsTo<V>) -> bool {
    (r1 == r2)
    && (((post1_perm).is_init() == (post2_perm).is_init()) && ((post1_perm).id() == (post2_perm).id()) && ((post1_perm).is_init() ==> ((post1_perm).value() == (post2_perm).value())))
}

proof fn det_put<V>(g__pre_perm__is_init___is_true: bool, g__pre_perm__is_init___is_false: bool, g__pre_perm__ptr___addr___eq: bool, k__pre_perm__ptr___addr___eq: int, g__pre_perm__ptr___addr___rng: bool, k__pre_perm__ptr___addr___rng_lo: int, k__pre_perm__ptr___addr___rng_hi: int, g__post1_perm__is_init___is_true: bool, g__post1_perm__is_init___is_false: bool, g__post1_perm__ptr___addr___eq: bool, k__post1_perm__ptr___addr___eq: int, g__post1_perm__ptr___addr___rng: bool, k__post1_perm__ptr___addr___rng_lo: int, k__post1_perm__ptr___addr___rng_hi: int, g__post2_perm__is_init___is_true: bool, g__post2_perm__is_init___is_false: bool, g__post2_perm__ptr___addr___eq: bool, k__post2_perm__ptr___addr___eq: int, g__post2_perm__ptr___addr___rng: bool, k__post2_perm__ptr___addr___rng_lo: int, k__post2_perm__ptr___addr___rng_hi: int, g_neq_tuple: bool, self_: &PCell<V>, pre_perm: PointsTo<V>, in_v: V, post1_perm: PointsTo<V>, r1: (), post2_perm: PointsTo<V>, r2: ())
    requires (pre_perm.id() == self_.id()), (pre_perm.mem_contents() == MemContents::Uninit),
    ensures
        ({
            &&& (post1_perm.id() == self_.id())
            &&& (post1_perm.mem_contents() == MemContents::Init(in_v))
            &&& (post2_perm.id() == self_.id())
            &&& (post2_perm.mem_contents() == MemContents::Init(in_v))
        }) ==> det_put_equal::<V>(r1, r2, post1_perm, post2_perm),
{
    if g__pre_perm__is_init___is_true { assume((pre_perm).is_init() == true); }
    if g__pre_perm__is_init___is_false { assume((pre_perm).is_init() == false); }
    if g__post1_perm__is_init___is_true { assume((post1_perm).is_init() == true); }
    if g__post1_perm__is_init___is_false { assume((post1_perm).is_init() == false); }
    if g__post2_perm__is_init___is_true { assume((post2_perm).is_init() == true); }
    if g__post2_perm__is_init___is_false { assume((post2_perm).is_init() == false); }
    if g_neq_tuple { assume(!det_put_equal::<V>(r1, r2, post1_perm, post2_perm)); }
}

}

fn main() {}
