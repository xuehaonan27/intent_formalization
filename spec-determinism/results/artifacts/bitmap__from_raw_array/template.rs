// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_from_raw_array_equal(r1: Result<Bitmap, Error>, r2: Result<Bitmap, Error>) -> bool {
    (((r1 is Ok) == (r2 is Ok)) && ((r1 is Ok) ==> ((r1->Ok_0)@ == (r2->Ok_0)@)))
}

proof fn det_from_raw_array(array: RawArray<u8>, r1: Result<Bitmap, Error>, r2: Result<Bitmap, Error>)
    requires (array.inv()), (array@.len() > 0), (array@.len() * (u8::BITS as usize) < u32::MAX as usize), (forall|i: int| 0 <= i < array@.len() ==> array@[i] == 0),
    ensures
        ({
            &&& (r1 matches Ok(bitmap) && {
                &&& bitmap.inv()
                &&& bitmap@.num_bits == array@.len() * (u8::BITS as int)
                &&& bitmap@.is_empty()
                &&& forall|i: int| 0 <= i < bitmap@.num_bits ==> !bitmap@.is_bit_set(i)
            })
            &&& (r2 matches Ok(bitmap) && {
                &&& bitmap.inv()
                &&& bitmap@.num_bits == array@.len() * (u8::BITS as int)
                &&& bitmap@.is_empty()
                &&& forall|i: int| 0 <= i < bitmap@.num_bits ==> !bitmap@.is_bit_set(i)
            })
        }) ==> det_from_raw_array_equal(r1, r2),
{
}