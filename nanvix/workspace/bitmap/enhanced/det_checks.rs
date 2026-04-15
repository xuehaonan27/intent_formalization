// ==========================================================================
// Bitmap Determinism Checks
// FAIL → nondeterminism → spec incomplete
// PASS → spec is deterministic for this function
// ==========================================================================

// DET-new: Bitmap::new determinism
proof fn det_new(
    number_of_bits: usize,
    result1: Result<Bitmap, Error>, result2: Result<Bitmap, Error>,
)
    ensures
        (
            // result1 satisfies new() ensures
            (result1 matches Ok(bitmap1) ==> {
                &&& bitmap1.inv()
                &&& bitmap1@.num_bits == number_of_bits as int
                &&& bitmap1@.is_empty()
            })
            && (number_of_bits == 0 ==> result1 is Err)
            && (number_of_bits >= u32::MAX ==> result1 is Err)
            && (number_of_bits % (u8::BITS as usize) != 0 ==> result1 is Err)

            // result2 also satisfies new() ensures
            && (result2 matches Ok(bitmap2) ==> {
                &&& bitmap2.inv()
                &&& bitmap2@.num_bits == number_of_bits as int
                &&& bitmap2@.is_empty()
            })
            && (number_of_bits == 0 ==> result2 is Err)
            && (number_of_bits >= u32::MAX ==> result2 is Err)
            && (number_of_bits % (u8::BITS as usize) != 0 ==> result2 is Err)
        )
        ==> result1 == result2
{
}

// DET-alloc: Bitmap::alloc determinism
proof fn det_alloc(
    pre: Bitmap,
    post1: Bitmap, post2: Bitmap,
    result1: Result<usize, Error>, result2: Result<usize, Error>,
)
    requires
        pre.inv(),
    ensures
        (
            // post1 satisfies alloc ensures
            post1.inv()
            && (match result1 {
                Ok(index) => {
                    &&& 0 <= index < post1@.num_bits
                    &&& post1@.num_bits == pre@.num_bits
                    &&& !pre@.is_bit_set(index as int)
                    &&& post1@.is_bit_set(index as int)
                    &&& forall|i: int|
                        0 <= i < post1@.num_bits && i != index ==>
                            post1@.is_bit_set(i) == pre@.is_bit_set(i)
                    &&& post1@.set_bits == pre@.set_bits.insert(index as int)
                    &&& post1@.usage() == pre@.usage() + 1
                },
                Err(_) => {
                    &&& pre@.is_full()
                    &&& post1@ == pre@
                },
            })

            // post2 also satisfies alloc ensures
            && post2.inv()
            && (match result2 {
                Ok(index) => {
                    &&& 0 <= index < post2@.num_bits
                    &&& post2@.num_bits == pre@.num_bits
                    &&& !pre@.is_bit_set(index as int)
                    &&& post2@.is_bit_set(index as int)
                    &&& forall|i: int|
                        0 <= i < post2@.num_bits && i != index ==>
                            post2@.is_bit_set(i) == pre@.is_bit_set(i)
                    &&& post2@.set_bits == pre@.set_bits.insert(index as int)
                    &&& post2@.usage() == pre@.usage() + 1
                },
                Err(_) => {
                    &&& pre@.is_full()
                    &&& post2@ == pre@
                },
            })
        )
        ==> (result1 == result2 && post1@ == post2@)
{
}

// DET-set: Bitmap::set determinism
proof fn det_set(
    pre: Bitmap, index: usize,
    post1: Bitmap, post2: Bitmap,
    result1: Result<(), Error>, result2: Result<(), Error>,
)
    requires
        pre.inv(),
    ensures
        (
            post1.inv()
            && (match result1 {
                Ok(()) => {
                    &&& index < post1@.num_bits
                    &&& post1@.is_bit_set(index as int)
                    &&& !pre@.is_bit_set(index as int)
                    &&& post1@.num_bits == pre@.num_bits
                    &&& forall|i: int|
                        0 <= i < post1@.num_bits && i != (index as int) ==>
                            post1@.is_bit_set(i) == pre@.is_bit_set(i)
                    &&& post1@.set_bits == pre@.set_bits.insert(index as int)
                    &&& post1@.usage() == pre@.usage() + 1
                },
                Err(_) => {
                    &&& index >= pre@.num_bits || pre@.is_bit_set(index as int)
                    &&& post1@ == pre@
                },
            })
            && post2.inv()
            && (match result2 {
                Ok(()) => {
                    &&& index < post2@.num_bits
                    &&& post2@.is_bit_set(index as int)
                    &&& !pre@.is_bit_set(index as int)
                    &&& post2@.num_bits == pre@.num_bits
                    &&& forall|i: int|
                        0 <= i < post2@.num_bits && i != (index as int) ==>
                            post2@.is_bit_set(i) == pre@.is_bit_set(i)
                    &&& post2@.set_bits == pre@.set_bits.insert(index as int)
                    &&& post2@.usage() == pre@.usage() + 1
                },
                Err(_) => {
                    &&& index >= pre@.num_bits || pre@.is_bit_set(index as int)
                    &&& post2@ == pre@
                },
            })
        )
        ==> (result1 == result2 && post1@ == post2@)
{
}
