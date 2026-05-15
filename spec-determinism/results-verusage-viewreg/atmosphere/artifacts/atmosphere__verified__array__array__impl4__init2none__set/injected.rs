use vstd::prelude::*;

fn main() {}

verus!{

// File: array.rs
pub struct Array<A, const N: usize>{
    pub seq: Ghost<Seq<A>>,
    pub ar: [A;N]
}

impl<A, const N: usize> Array<A, N> {

    #[verifier(inline)]
    pub open spec fn view(&self) -> Seq<A>{
        self.seq@
    }

    pub open spec fn wf(&self) -> bool{
        self.seq@.len() == N
    }

}


impl<A, const N: usize> Array<A, N> {

    #[verifier(external_body)]
    pub fn set(&mut self, i: usize, out: A)
        requires
            0 <= i < N,
            old(self).wf(),
        ensures
            self.seq@ =~= old(self).seq@.update(i as int, out),
            self.wf(),
	{
		unimplemented!()
	}

}


impl<T: Copy, const N: usize> Array<Option<T>, N> {

    pub fn init2none(&mut self)
        requires
            old(self).wf(),
            N <= usize::MAX,
        ensures
            forall|index:int| 0<= index < N ==> #[trigger] self@[index].is_None(),
            self.wf(),
    {
        let mut i = 0;
        for i in 0..N
            invariant
                N <= usize::MAX,
                0<=i<=N,
                self.wf(),
                forall|j:int| #![auto] 0<=j<i ==> self@[j].is_None(),
        {
            let tmp:Ghost<Seq<Option<T>>> = Ghost(self@);
            assert(forall|j:int| #![auto] 0<=j<i ==> self@[j].is_None());
            self.set(i,None);
            assert(self@ =~= tmp@.update(i as int,None));
            assert(forall|j:int| #![auto] 0<=j<i ==> self@[j].is_None());
        }
    }

}




// === INJECTED DET CHECK ===
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_set_equal<A, const N: usize>(r1: (), r2: (), post1_self_: Array<A, N>, post2_self_: Array<A, N>) -> bool {
    (r1 == r2)
    && (post1_self_ == post2_self_)
}

proof fn det_set<A, const N: usize>(g_i_eq: bool, k_i_eq: int, g_i_rng: bool, k_i_rng_lo: int, k_i_rng_hi: int, g_neq_tuple: bool, pre_self_: Array<A, N>, i: usize, out: A, post1_self_: Array<A, N>, r1: (), post2_self_: Array<A, N>, r2: ())
    requires (0 <= i < N), (pre_self_.wf()),
    ensures
        ({
            &&& (post1_self_.seq@ =~= pre_self_.seq@.update(i as int, out))
            &&& (post1_self_.wf())
            &&& (post2_self_.seq@ =~= pre_self_.seq@.update(i as int, out))
            &&& (post2_self_.wf())
        }) ==> det_set_equal(r1, r2, post1_self_, post2_self_),
{
    if g_i_eq { assume(i as int == k_i_eq); }
    if g_i_rng { assume(i as int >= k_i_rng_lo && i as int <= k_i_rng_hi); }
    if g_neq_tuple { assume(!det_set_equal(r1, r2, post1_self_, post2_self_)); }
}
// === END INJECTED ===

}
