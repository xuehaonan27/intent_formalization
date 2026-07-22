#![allow(unused_imports)]
extern crate alloc;
use vstd::prelude::*;
use vstd::atomic::*;


verus! {
spec fn det_fetch_xor_equal<T>(r1: *mut T, r2: *mut T, post1_perm: PermissionPtr<T>, post2_perm: PermissionPtr<T>) -> bool {
    (true /* raw pointer: opaque by default */)
    && (post1_perm.view() == post2_perm.view())
}


proof fn det_fetch_xor<T>(g_n_eq: bool, k_n_eq: int, g_n_rng: bool, k_n_rng_lo: int, k_n_rng_hi: int, g_neq_tuple: bool, self_: &PAtomicPtr<T>, pre_perm: PermissionPtr<T>, n: usize, post1_perm: PermissionPtr<T>, r1: *mut T, post2_perm: PermissionPtr<T>, r2: *mut T)
    requires (equal(self_.id(), pre_perm.view().patomic)),
    ensures
        ({
            &&& (equal(pre_perm.view().value, r1))
            &&& (post1_perm.view().patomic == pre_perm.view().patomic)
            &&& (post1_perm.view().value@.addr == (pre_perm.view().value@.addr ^ n))
            &&& (post1_perm.view().value@.provenance == pre_perm.view().value@.provenance)
            &&& (post1_perm.view().value@.metadata == pre_perm.view().value@.metadata)
            &&& (equal(pre_perm.view().value, r2))
            &&& (post2_perm.view().patomic == pre_perm.view().patomic)
            &&& (post2_perm.view().value@.addr == (pre_perm.view().value@.addr ^ n))
            &&& (post2_perm.view().value@.provenance == pre_perm.view().value@.provenance)
            &&& (post2_perm.view().value@.metadata == pre_perm.view().value@.metadata)
        }) ==> det_fetch_xor_equal::<T>(r1, r2, post1_perm, post2_perm),
{
    if g_n_eq { assume(n as int == k_n_eq); }
    if g_n_rng { assume(n as int >= k_n_rng_lo && n as int <= k_n_rng_hi); }
    if g_neq_tuple { assume(!det_fetch_xor_equal::<T>(r1, r2, post1_perm, post2_perm)); }
}
}

fn main() {}
