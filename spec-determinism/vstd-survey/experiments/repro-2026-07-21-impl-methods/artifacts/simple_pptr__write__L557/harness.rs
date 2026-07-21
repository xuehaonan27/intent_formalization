#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::simple_pptr::*;


verus! {
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_write_equal<V>(r1: (), r2: (), post1_perm: PointsTo<V>, post2_perm: PointsTo<V>) -> bool
    where V: Copy {
    (r1 == r2)
    && (((post1_perm).is_init() == (post2_perm).is_init()) && ((post1_perm).pptr().addr() == (post2_perm).pptr().addr()) && ((post1_perm).is_init() ==> ((post1_perm).value() == (post2_perm).value())))
}

proof fn det_write<V>(g__pre_perm__is_init___is_true: bool, g__pre_perm__is_init___is_false: bool, g__pre_perm__addr___eq: bool, k__pre_perm__addr___eq: int, g__pre_perm__addr___rng: bool, k__pre_perm__addr___rng_lo: int, k__pre_perm__addr___rng_hi: int, g__post1_perm__is_init___is_true: bool, g__post1_perm__is_init___is_false: bool, g__post1_perm__addr___eq: bool, k__post1_perm__addr___eq: int, g__post1_perm__addr___rng: bool, k__post1_perm__addr___rng_lo: int, k__post1_perm__addr___rng_hi: int, g__post2_perm__is_init___is_true: bool, g__post2_perm__is_init___is_false: bool, g__post2_perm__addr___eq: bool, k__post2_perm__addr___eq: int, g__post2_perm__addr___rng: bool, k__post2_perm__addr___rng_lo: int, k__post2_perm__addr___rng_hi: int, g_neq_tuple: bool, self_: PPtr<V>, pre_perm: PointsTo<V>, in_v: V, post1_perm: PointsTo<V>, r1: (), post2_perm: PointsTo<V>, r2: ())
    where V: Copy
    requires (pre_perm.pptr() == self_),
    ensures
        ({
            &&& (post1_perm.pptr() == pre_perm.pptr())
            &&& (post1_perm.mem_contents() == MemContents::Init(in_v))
            &&& (post2_perm.pptr() == pre_perm.pptr())
            &&& (post2_perm.mem_contents() == MemContents::Init(in_v))
        }) ==> det_write_equal::<V>(r1, r2, post1_perm, post2_perm),
{
    if g__pre_perm__is_init___is_true { assume((pre_perm).is_init() == true); }
    if g__pre_perm__is_init___is_false { assume((pre_perm).is_init() == false); }
    if g__pre_perm__addr___eq { assume((pre_perm).addr() as int == k__pre_perm__addr___eq); }
    if g__pre_perm__addr___rng { assume((pre_perm).addr() as int >= k__pre_perm__addr___rng_lo && (pre_perm).addr() as int <= k__pre_perm__addr___rng_hi); }
    if g__post1_perm__is_init___is_true { assume((post1_perm).is_init() == true); }
    if g__post1_perm__is_init___is_false { assume((post1_perm).is_init() == false); }
    if g__post1_perm__addr___eq { assume((post1_perm).addr() as int == k__post1_perm__addr___eq); }
    if g__post1_perm__addr___rng { assume((post1_perm).addr() as int >= k__post1_perm__addr___rng_lo && (post1_perm).addr() as int <= k__post1_perm__addr___rng_hi); }
    if g__post2_perm__is_init___is_true { assume((post2_perm).is_init() == true); }
    if g__post2_perm__is_init___is_false { assume((post2_perm).is_init() == false); }
    if g__post2_perm__addr___eq { assume((post2_perm).addr() as int == k__post2_perm__addr___eq); }
    if g__post2_perm__addr___rng { assume((post2_perm).addr() as int >= k__post2_perm__addr___rng_lo && (post2_perm).addr() as int <= k__post2_perm__addr___rng_hi); }
    if g_neq_tuple { assume(!det_write_equal(r1, r2, post1_perm, post2_perm)); }
}
}

fn main() {}
