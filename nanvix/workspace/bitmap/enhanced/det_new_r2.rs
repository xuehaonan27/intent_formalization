// R2a: number_of_bits < 100?
proof fn det_new_r2a(
    number_of_bits: usize,
    result1: Result<Bitmap, Error>, result2: Result<Bitmap, Error>,
)
    ensures
        (
            (result1 matches Ok(bitmap1) ==> {
                &&& bitmap1.inv()
                &&& bitmap1@.num_bits == number_of_bits as int
                &&& bitmap1@.is_empty()
            })
            && (number_of_bits == 0 ==> result1 is Err)
            && (number_of_bits >= u32::MAX ==> result1 is Err)
            && (number_of_bits % (u8::BITS as usize) != 0 ==> result1 is Err)
            && (result2 matches Ok(bitmap2) ==> {
                &&& bitmap2.inv()
                &&& bitmap2@.num_bits == number_of_bits as int
                &&& bitmap2@.is_empty()
            })
            && (number_of_bits == 0 ==> result2 is Err)
            && (number_of_bits >= u32::MAX ==> result2 is Err)
            && (number_of_bits % (u8::BITS as usize) != 0 ==> result2 is Err)
            && number_of_bits < 100
        )
        ==> (result1 is Ok <==> result2 is Ok)
{
}

// R2b: number_of_bits == 8 specifically?
proof fn det_new_r2b(
    number_of_bits: usize,
    result1: Result<Bitmap, Error>, result2: Result<Bitmap, Error>,
)
    ensures
        (
            (result1 matches Ok(bitmap1) ==> {
                &&& bitmap1.inv()
                &&& bitmap1@.num_bits == number_of_bits as int
                &&& bitmap1@.is_empty()
            })
            && (number_of_bits == 0 ==> result1 is Err)
            && (number_of_bits >= u32::MAX ==> result1 is Err)
            && (number_of_bits % (u8::BITS as usize) != 0 ==> result1 is Err)
            && (result2 matches Ok(bitmap2) ==> {
                &&& bitmap2.inv()
                &&& bitmap2@.num_bits == number_of_bits as int
                &&& bitmap2@.is_empty()
            })
            && (number_of_bits == 0 ==> result2 is Err)
            && (number_of_bits >= u32::MAX ==> result2 is Err)
            && (number_of_bits % (u8::BITS as usize) != 0 ==> result2 is Err)
            && number_of_bits == 8
        )
        ==> (result1 is Ok <==> result2 is Ok)
{
}

// R2c: what about invalid inputs? number_of_bits == 0?
proof fn det_new_r2c(
    number_of_bits: usize,
    result1: Result<Bitmap, Error>, result2: Result<Bitmap, Error>,
)
    ensures
        (
            (result1 matches Ok(bitmap1) ==> {
                &&& bitmap1.inv()
                &&& bitmap1@.num_bits == number_of_bits as int
                &&& bitmap1@.is_empty()
            })
            && (number_of_bits == 0 ==> result1 is Err)
            && (number_of_bits >= u32::MAX ==> result1 is Err)
            && (number_of_bits % (u8::BITS as usize) != 0 ==> result1 is Err)
            && (result2 matches Ok(bitmap2) ==> {
                &&& bitmap2.inv()
                &&& bitmap2@.num_bits == number_of_bits as int
                &&& bitmap2@.is_empty()
            })
            && (number_of_bits == 0 ==> result2 is Err)
            && (number_of_bits >= u32::MAX ==> result2 is Err)
            && (number_of_bits % (u8::BITS as usize) != 0 ==> result2 is Err)
            && number_of_bits == 0
        )
        ==> (result1 is Ok <==> result2 is Ok)
{
}
