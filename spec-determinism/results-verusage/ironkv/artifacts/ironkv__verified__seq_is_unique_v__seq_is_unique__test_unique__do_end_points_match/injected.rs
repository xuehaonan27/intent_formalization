use vstd::prelude::*;

fn main() {}


verus! {

pub struct AbstractEndPoint {
    pub id: Seq<u8>,
}

// #[derive(Copy, Clone)]
#[derive(PartialEq, Eq, Hash)]
pub struct EndPoint {
    pub id: Vec<u8>,
}

impl EndPoint {

    pub open spec fn view(self) -> AbstractEndPoint {
        AbstractEndPoint{id: self.id@}
    }
}


pub open spec fn abstractify_end_points(end_points: Vec<EndPoint>) -> Seq<AbstractEndPoint>
{
    end_points@.map(|i, end_point: EndPoint| end_point@)
}


#[verifier::opaque]
    pub open spec fn seq_is_unique<T>(s: Seq<T>) -> bool
    {
        forall |i: int, j: int| #![trigger s[i], s[j]] 0 <= i && i < s.len() && 0 <= j && j < s.len() && s[i] == s[j] ==> i == j
    }

    #[verifier::external_body]
pub fn do_end_points_match(e1: &EndPoint, e2: &EndPoint) -> (eq: bool)
    ensures
eq == (e1@ == e2@)
{
    unimplemented!()
}

pub fn test_unique(endpoints: &Vec<EndPoint>) -> (unique: bool)
    ensures
    unique == seq_is_unique(abstractify_end_points(*endpoints)),
{
    let mut i: usize = 0;
    while i < endpoints.len()
        invariant
            0 <= i,
            i <= endpoints.len(),
            forall |j: int, k: int| #![trigger endpoints@[j]@, endpoints@[k]@]
                0 <= j && j < endpoints.len() && 0 <= k && k < i && j != k ==> endpoints@[j]@ != endpoints@[k]@,
                decreases
                    endpoints.len() - i
                    {
                        let mut j: usize = 0;
                        while j < endpoints.len()
                            invariant
                                0 <= i,
                                i < endpoints.len(),
                                forall |j: int, k: int| #![trigger endpoints@[j]@, endpoints@[k]@]
                                    0 <= j && j < endpoints.len() && 0 <= k && k < i && j != k ==> endpoints@[j]@ != endpoints@[k]@,
                                    0 <= j,
                                    j <= endpoints.len(),
                                    forall |k: int| #![trigger endpoints@[k]@] 0 <= k && k < j && k != i ==> endpoints@[i as int]@ != endpoints@[k]@,
                                    decreases
                                        endpoints.len() - j
                                        {
                                            if i != j && do_end_points_match(&endpoints[i], &endpoints[j]) {
                                                assert (!seq_is_unique(abstractify_end_points(*endpoints))) by {
                                                    reveal(seq_is_unique::<AbstractEndPoint>);
                                                    let aeps = abstractify_end_points(*endpoints);
                                                    assert (aeps[i as int] == endpoints@[i as int]@);
                                                    assert (aeps[j as int] == endpoints@[j as int]@);
                                                    assert (endpoints@[i as int]@ == endpoints@[j as int]@ && i != j);
                                                }
                                                return false;
                                            }
                                            j = j + 1;
                                        }
                        i = i + 1;
                    };
    assert (seq_is_unique(abstractify_end_points(*endpoints))) by {
        reveal(seq_is_unique::<AbstractEndPoint>);
    }
    return true;
}


// === INJECTED DET CHECK ===
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_do_end_points_match_equal(r1: bool, r2: bool) -> bool {
    (r1 == r2)
}

proof fn det_do_end_points_match(g_r1_is_true: bool, g_r1_is_false: bool, g_r2_is_true: bool, g_r2_is_false: bool, g_neq_tuple: bool, e1: EndPoint, e2: EndPoint, r1: bool, r2: bool)
    ensures
        ({
            &&& (r1 == (e1@ == e2@))
            &&& (r2 == (e1@ == e2@))
        }) ==> det_do_end_points_match_equal(r1, r2),
{
    if g_r1_is_true { assume(r1 == true); }
    if g_r1_is_false { assume(r1 == false); }
    if g_r2_is_true { assume(r2 == true); }
    if g_r2_is_false { assume(r2 == false); }
    if g_neq_tuple { assume(!det_do_end_points_match_equal(r1, r2)); }
}
// === END INJECTED ===

}
