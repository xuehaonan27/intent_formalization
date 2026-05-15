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



// File: array_set.rs
pub struct ArraySet<const N: usize> {
    pub data: Array<bool, N>,
    pub len: usize,

    pub set: Ghost<Set<usize>>,
}

impl <const N: usize> ArraySet<N> {

    pub closed spec fn view(&self) -> Set<usize>{
        self.set@
    }

    pub closed spec fn wf(&self) -> bool{
        &&&
        self.data.wf()
        &&&
        self.set@.finite()
        &&&
        0 <= self.len <= N
        &&&
        forall|i:usize| 
            #![trigger self.data@[i as int]]
            #![trigger self.set@.contains(i)]
            0 <= i < N && self.data@[i as int] ==> self.set@.contains(i)
        &&&
        forall|i:usize| 
            #![trigger self.data@[i as int]]
            #![trigger self.set@.contains(i)]
            self.set@.contains(i) ==> 0 <= i < N && self.data@[i as int]     
        &&&
        self.len == self.set@.len() 
    }

    pub fn init(&mut self)
        requires
            old(self).wf(),
        ensures
            self.wf(),
            self@ == Set::<usize>::empty(),
    {
            self.len = 0;
            self.set = Ghost(Set::<usize>::empty());
        for i in 0..N
            invariant
                0<=i<=N,
                self.data.wf(),
                self.len == 0,
                self.set@ == Set::<usize>::empty(),
                forall|j:int|
                    0<=j<i ==> self.data@[j] == false,
        {
            self.data.set(i,false);
        }
    }


}




// === INJECTED DET CHECK ===
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_init_equal<const N: usize>(r1: (), r2: (), post1_self_: ArraySet<N>, post2_self_: ArraySet<N>) -> bool {
    (r1 == r2)
    && (post1_self_ == post2_self_)
}

proof fn det_init<const N: usize>(g_neq_tuple: bool, pre_self_: ArraySet<N>, post1_self_: ArraySet<N>, r1: (), post2_self_: ArraySet<N>, r2: ())
    requires (pre_self_.wf()),
    ensures
        ({
            &&& (post1_self_.wf())
            &&& (post1_self_@ == Set::<usize>::empty())
            &&& (post2_self_.wf())
            &&& (post2_self_@ == Set::<usize>::empty())
        }) ==> det_init_equal(r1, r2, post1_self_, post2_self_),
{
    if g_neq_tuple { assume(!det_init_equal(r1, r2, post1_self_, post2_self_)); }
}
// === END INJECTED ===

}
