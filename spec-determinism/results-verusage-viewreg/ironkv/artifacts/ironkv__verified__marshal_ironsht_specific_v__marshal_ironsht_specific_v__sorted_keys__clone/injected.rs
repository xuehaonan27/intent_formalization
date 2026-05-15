use vstd::prelude::*;

fn main() {}

verus! {
#[derive(Eq,PartialEq,Hash)]
pub struct SHTKey {
    pub // workaround
        ukey: u64,
}

impl SHTKey {
    pub fn clone(&self) -> (out: SHTKey)
    ensures out == self
    {
        SHTKey{ ukey: self.ukey }
    }
}

pub type AbstractKey = SHTKey;
pub type CKey = SHTKey;


pub struct CKeyKV {
    pub k: CKey,
    pub v: Vec<u8>,
}

impl CKeyKV {
    pub open spec fn view(self) -> (AbstractKey, Seq<u8>)
    {
        (self.k, self.v@)
    }
}
pub open spec fn ckeykvlt(a: CKeyKV, b: CKeyKV) -> bool {
    a.k.ukey < b.k.ukey
}

pub open spec fn spec_sorted_keys(v: Vec<CKeyKV>) -> bool {
    // ckeykvlt ensures that this forall does not create a trigger loop on
    // v@[i].k.ukey, v@[i+1].k.ukey, ...
    //
    // we weren't able to fix this by making the whole < the trigger
    forall |i: int, j: int| 0 <= i && i + 1 < v.len() && j == i+1 ==> #[trigger] ckeykvlt(v@[i], v@[j])
}

pub exec fn sorted_keys(v: &Vec<CKeyKV>) -> (res: bool)
    ensures res == spec_sorted_keys(*v),
{
    if v.len() <= 1 {
        true
    } else {
        let mut idx = 1;
        while idx < v.len()
            invariant
                (0 < idx <= v.len()),
                (forall |i: int, j: int| 0 <= i && i + 1 < idx && j == i+1 ==> #[trigger] ckeykvlt(v@[i], v@[j])),
                decreases
                    v.len() - idx
                    {
                        if v[idx - 1].k.ukey >= v[idx].k.ukey {
                            assert(!ckeykvlt(v@[idx as int-1], v@[idx as int]));
                            return false;
                        } else {
                            idx = idx + 1;
                        }
                    }
        assert forall |i: int| 0 <= i && i + 1 < v.len() implies #[trigger] v@[i].k.ukey < v@[i + 1].k.ukey by {
            assert(ckeykvlt(v@[i], v@[i + 1])); // OBSERVE
        }
        true
    }
}


// === INJECTED DET CHECK ===
// L4-llm view declarations (generated, see view_registry cache)
pub struct SHTKeyView { pub ukey: u64 }

impl View for SHTKey {
    type V = SHTKeyView;
    closed spec fn view(&self) -> SHTKeyView {
        SHTKeyView { ukey: self.ukey }
    }
}

// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_clone_equal(r1: SHTKey, r2: SHTKey) -> bool {
    (((r1).view() == (r2).view()))
}

proof fn det_clone(g_self__ukey_eq: bool, k_self__ukey_eq: int, g_self__ukey_rng: bool, k_self__ukey_rng_lo: int, k_self__ukey_rng_hi: int, g_neq_tuple: bool, self_: SHTKey, r1: SHTKey, r2: SHTKey)
    ensures
        ({
            &&& (r1 == self_)
            &&& (r2 == self_)
        }) ==> det_clone_equal(r1, r2),
{
    if g_self__ukey_eq { assume(self_.ukey as int == k_self__ukey_eq); }
    if g_self__ukey_rng { assume(self_.ukey as int >= k_self__ukey_rng_lo && self_.ukey as int <= k_self__ukey_rng_hi); }
    if g_neq_tuple { assume(!det_clone_equal(r1, r2)); }
}
// === END INJECTED ===

}
