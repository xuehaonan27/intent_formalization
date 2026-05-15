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


    #[verifier::external_body]
pub fn do_end_points_match(e1: &EndPoint, e2: &EndPoint) -> (eq: bool)
    ensures
eq == (e1@ == e2@)
{
    unimplemented!()
}

pub fn endpoints_contain(endpoints: &Vec<EndPoint>, endpoint: &EndPoint) -> (present: bool)
ensures present == abstractify_end_points(*endpoints).contains(endpoint@)
    {
        let mut j: usize = 0;
        while j < endpoints.len()
            invariant
                0 <= j && j <= endpoints.len(),
                forall |k: int| #![trigger endpoints@[k]@] 0 <= k && k < j ==> endpoint@ != endpoints@[k]@,
                decreases
                    endpoints.len() - j
                    {
                        if do_end_points_match(endpoint, &endpoints[j]) {
                            assert (abstractify_end_points(*endpoints)[j as int] == endpoint@);
                            return true;
                        }
                        j = j + 1;
                    }
        return false;
    }


// === INJECTED DET CHECK ===
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_endpoints_contain_equal(r1: bool, r2: bool) -> bool {
    (r1 == r2)
}

proof fn det_endpoints_contain(g_r1_is_true: bool, g_r1_is_false: bool, g_r2_is_true: bool, g_r2_is_false: bool, g_neq_tuple: bool, endpoints: Vec<EndPoint>, endpoint: EndPoint, r1: bool, r2: bool)
    ensures
        ({
            &&& (r1 == abstractify_end_points(endpoints).contains(endpoint@))
            &&& (r2 == abstractify_end_points(endpoints).contains(endpoint@))
        }) ==> det_endpoints_contain_equal(r1, r2),
{
    if g_r1_is_true { assume(r1 == true); }
    if g_r1_is_false { assume(r1 == false); }
    if g_r2_is_true { assume(r2 == true); }
    if g_r2_is_false { assume(r2 == false); }
    if g_neq_tuple { assume(!det_endpoints_contain_equal(r1, r2)); }
}
// === END INJECTED ===

}
