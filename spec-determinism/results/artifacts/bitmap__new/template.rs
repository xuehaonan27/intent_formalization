// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_new_equal(r1: Result<Bitmap, Error>, r2: Result<Bitmap, Error>) -> bool {
    (((r1 is Ok) == (r2 is Ok)) && ((r1 is Ok) ==> ((r1->Ok_0)@ == (r2->Ok_0)@)))
}

proof fn det_new(number_of_bits: usize, r1: Result<Bitmap, Error>, r2: Result<Bitmap, Error>)
    ensures
        ({
            &&& (r1 matches Ok(bitmap_1) ==> {
                &&& bitmap_1.inv()
                &&& bitmap_1@.num_bits == number_of_bits as int
                &&& bitmap_1@.is_empty()
            })
            &&& (number_of_bits == 0 ==> r1 is Err)
            &&& (number_of_bits >= u32::MAX ==> r1 is Err)
            &&& (number_of_bits % (u8::BITS as usize) != 0 ==> r1 is Err)
            &&& (r2 matches Ok(bitmap_2) ==> {
                &&& bitmap_2.inv()
                &&& bitmap_2@.num_bits == number_of_bits as int
                &&& bitmap_2@.is_empty()
            })
            &&& (number_of_bits == 0 ==> r2 is Err)
            &&& (number_of_bits >= u32::MAX ==> r2 is Err)
            &&& (number_of_bits % (u8::BITS as usize) != 0 ==> r2 is Err)
        }) ==> det_new_equal(r1, r2),
{
}