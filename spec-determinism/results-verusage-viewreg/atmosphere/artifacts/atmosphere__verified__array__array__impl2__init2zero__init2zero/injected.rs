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


impl<const N: usize> Array<u8, N> {

    pub fn init2zero(&mut self)
        requires
            old(self).wf(),
            N <= usize::MAX,
        ensures
            forall|index:int| 0<= index < N ==> #[trigger] self@[index] == 0,
            self.wf(),
    {
        let mut i = 0;
        for i in 0..N
            invariant
                N <= usize::MAX,
                0<=i<=N,
                self.wf(),
                forall|j:int| #![auto] 0<=j<i ==> self@[j] == 0,
        {
            let tmp:Ghost<Seq<u8>> = Ghost(self@);
            assert(forall|j:int| #![auto] 0<=j<i ==> self@[j] == 0);
            self.set(i,0);
            assert(self@ =~= tmp@.update(i as int,0));
            assert(forall|j:int| #![auto] 0<=j<i ==> self@[j] == 0);
        }
    }

}


// === INJECTED DET CHECK ===
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_init2zero_equal<const N: usize>(r1: (), r2: (), post1_self_: Array<u8, N>, post2_self_: Array<u8, N>) -> bool {
    (r1 == r2)
    && (post1_self_ == post2_self_)
}

proof fn det_init2zero<const N: usize>(g_neq_tuple: bool, pre_self_: Array<u8, N>, post1_self_: Array<u8, N>, r1: (), post2_self_: Array<u8, N>, r2: ())
    requires (pre_self_.wf()), (N <= usize::MAX),
    ensures
        ({
            &&& (forall|index:int| 0<= index < N ==> #[trigger] post1_self_@[index] == 0)
            &&& (post1_self_.wf())
            &&& (forall|index:int| 0<= index < N ==> #[trigger] post2_self_@[index] == 0)
            &&& (post2_self_.wf())
        }) ==> det_init2zero_equal(r1, r2, post1_self_, post2_self_),
{
    if g_neq_tuple { assume(!det_init2zero_equal(r1, r2, post1_self_, post2_self_)); }
}
// === END INJECTED ===

}
