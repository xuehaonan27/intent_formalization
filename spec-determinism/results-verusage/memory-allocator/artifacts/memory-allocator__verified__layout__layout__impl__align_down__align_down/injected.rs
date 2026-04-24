use vstd::prelude::*;


fn main () {}

verus! {

	#[verifier::external_body]
proof fn bitand_with_mask_gives_rounding(x: usize, y: usize)
    requires y != 0, y & sub(y, 1) == 0,
    ensures x & !sub(y, 1) == (x / y) * y,
    decreases y,
	{
		unimplemented!()
	}

	#[verifier::external_body]
pub proof fn mul_mod_right(a: int, b: int)
    requires b != 0,
    ensures (a * b) % b == 0,
	{
		unimplemented!()
	}

#[inline]
pub fn align_down(x: usize, y: usize) -> (res: usize)
    requires y != 0,
    ensures
        res == (x as int / y as int) * y,
        res <= x < res + y,
        res % y == 0,
        (res / y * y) == res,
{
    let mask = y - 1;

    proof {
        assert(0 <= (x / y) * y <= x) by(nonlinear_arith)
            requires y > 0, x >= 0;

        //assert((y & mask) == 0usize ==> (x & !mask) == sub(x, x % y)) by(bit_vector)
        //    requires mask == sub(y, 1), y >= 1usize;
        if y & mask == 0usize {
            bitand_with_mask_gives_rounding(x, y);
            assert((x & !mask) == (x / y) * y);
            assert((x & !mask) == (x as int / y as int) * y);
        }

        assert((x as int / y as int) == (x / y) as int);

        assert(x / y * y + x % y == x) by(nonlinear_arith) requires y != 0;
        assert(0 <= x % y < y);
        let t = x / y;
        mul_mod_right(t as int, y as int);
        assert(y != 0 ==> (t * y) / y as int * y == t * y) by(nonlinear_arith);
    }

    if ((y & mask) == 0) { // power of two?
        x & !mask
    } else {
        (x / y) * y
    }
}


// === INJECTED DET CHECK ===
// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_align_down_equal(r1: usize, r2: usize) -> bool {
    (r1 == r2)
}

proof fn det_align_down(g_x_eq: bool, k_x_eq: int, g_x_rng: bool, k_x_rng_lo: int, k_x_rng_hi: int, g_y_eq: bool, k_y_eq: int, g_y_rng: bool, k_y_rng_lo: int, k_y_rng_hi: int, g_r1_eq: bool, k_r1_eq: int, g_r1_rng: bool, k_r1_rng_lo: int, k_r1_rng_hi: int, g_r2_eq: bool, k_r2_eq: int, g_r2_rng: bool, k_r2_rng_lo: int, k_r2_rng_hi: int, g_neq_tuple: bool, x: usize, y: usize, r1: usize, r2: usize)
    requires (y != 0),
    ensures
        ({
            &&& (r1 == (x as int / y as int) * y)
            &&& (r1 <= x < r1 + y)
            &&& (r1 % y == 0)
            &&& ((r1 / y * y) == r1)
            &&& (r2 == (x as int / y as int) * y)
            &&& (r2 <= x < r2 + y)
            &&& (r2 % y == 0)
            &&& ((r2 / y * y) == r2)
        }) ==> det_align_down_equal(r1, r2),
{
    if g_x_eq { assume(x as int == k_x_eq); }
    if g_x_rng { assume(x as int >= k_x_rng_lo && x as int <= k_x_rng_hi); }
    if g_y_eq { assume(y as int == k_y_eq); }
    if g_y_rng { assume(y as int >= k_y_rng_lo && y as int <= k_y_rng_hi); }
    if g_r1_eq { assume(r1 as int == k_r1_eq); }
    if g_r1_rng { assume(r1 as int >= k_r1_rng_lo && r1 as int <= k_r1_rng_hi); }
    if g_r2_eq { assume(r2 as int == k_r2_eq); }
    if g_r2_rng { assume(r2 as int >= k_r2_rng_lo && r2 as int <= k_r2_rng_hi); }
    if g_neq_tuple { assume(!det_align_down_equal(r1, r2)); }
}
// === END INJECTED ===

}
