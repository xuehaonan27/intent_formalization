// ALLOC R1: same branch? (Ok vs Err)
proof fn det_alloc_r1_branch(
    pre: Bitmap, post1: Bitmap, post2: Bitmap,
    result1: Result<usize, Error>, result2: Result<usize, Error>,
)
    requires pre.inv(),
    ensures
        (
            post1.inv()
            && (match result1 {
                Ok(index) => {
                    &&& 0 <= index < post1@.num_bits
                    &&& post1@.num_bits == pre@.num_bits
                    &&& !pre@.is_bit_set(index as int)
                    &&& post1@.is_bit_set(index as int)
                    &&& forall|i: int| 0 <= i < post1@.num_bits && i != index ==> post1@.is_bit_set(i) == pre@.is_bit_set(i)
                    &&& post1@.set_bits == pre@.set_bits.insert(index as int)
                    &&& post1@.usage() == pre@.usage() + 1
                },
                Err(_) => { &&& pre@.is_full() &&& post1@ == pre@ },
            })
            && post2.inv()
            && (match result2 {
                Ok(index) => {
                    &&& 0 <= index < post2@.num_bits
                    &&& post2@.num_bits == pre@.num_bits
                    &&& !pre@.is_bit_set(index as int)
                    &&& post2@.is_bit_set(index as int)
                    &&& forall|i: int| 0 <= i < post2@.num_bits && i != index ==> post2@.is_bit_set(i) == pre@.is_bit_set(i)
                    &&& post2@.set_bits == pre@.set_bits.insert(index as int)
                    &&& post2@.usage() == pre@.usage() + 1
                },
                Err(_) => { &&& pre@.is_full() &&& post2@ == pre@ },
            })
        )
        ==> (result1 is Ok <==> result2 is Ok)
{
}

// ALLOC R2: given both Ok, same index?
proof fn det_alloc_r2_index(
    pre: Bitmap, post1: Bitmap, post2: Bitmap,
    result1: Result<usize, Error>, result2: Result<usize, Error>,
)
    requires pre.inv(),
    ensures
        (
            post1.inv()
            && (match result1 {
                Ok(index) => {
                    &&& 0 <= index < post1@.num_bits
                    &&& post1@.num_bits == pre@.num_bits
                    &&& !pre@.is_bit_set(index as int)
                    &&& post1@.is_bit_set(index as int)
                    &&& forall|i: int| 0 <= i < post1@.num_bits && i != index ==> post1@.is_bit_set(i) == pre@.is_bit_set(i)
                    &&& post1@.set_bits == pre@.set_bits.insert(index as int)
                    &&& post1@.usage() == pre@.usage() + 1
                },
                Err(_) => { &&& pre@.is_full() &&& post1@ == pre@ },
            })
            && post2.inv()
            && (match result2 {
                Ok(index) => {
                    &&& 0 <= index < post2@.num_bits
                    &&& post2@.num_bits == pre@.num_bits
                    &&& !pre@.is_bit_set(index as int)
                    &&& post2@.is_bit_set(index as int)
                    &&& forall|i: int| 0 <= i < post2@.num_bits && i != index ==> post2@.is_bit_set(i) == pre@.is_bit_set(i)
                    &&& post2@.set_bits == pre@.set_bits.insert(index as int)
                    &&& post2@.usage() == pre@.usage() + 1
                },
                Err(_) => { &&& pre@.is_full() &&& post2@ == pre@ },
            })
            && result1 is Ok
            && result2 is Ok
        )
        ==> result1 == result2
{
}

// ALLOC R3: given both Ok + same index, same post-state?
proof fn det_alloc_r3_post(
    pre: Bitmap, post1: Bitmap, post2: Bitmap,
    result1: Result<usize, Error>, result2: Result<usize, Error>,
)
    requires pre.inv(),
    ensures
        (
            post1.inv()
            && (match result1 {
                Ok(index) => {
                    &&& 0 <= index < post1@.num_bits
                    &&& post1@.num_bits == pre@.num_bits
                    &&& !pre@.is_bit_set(index as int)
                    &&& post1@.is_bit_set(index as int)
                    &&& forall|i: int| 0 <= i < post1@.num_bits && i != index ==> post1@.is_bit_set(i) == pre@.is_bit_set(i)
                    &&& post1@.set_bits == pre@.set_bits.insert(index as int)
                    &&& post1@.usage() == pre@.usage() + 1
                },
                Err(_) => { &&& pre@.is_full() &&& post1@ == pre@ },
            })
            && post2.inv()
            && (match result2 {
                Ok(index) => {
                    &&& 0 <= index < post2@.num_bits
                    &&& post2@.num_bits == pre@.num_bits
                    &&& !pre@.is_bit_set(index as int)
                    &&& post2@.is_bit_set(index as int)
                    &&& forall|i: int| 0 <= i < post2@.num_bits && i != index ==> post2@.is_bit_set(i) == pre@.is_bit_set(i)
                    &&& post2@.set_bits == pre@.set_bits.insert(index as int)
                    &&& post2@.usage() == pre@.usage() + 1
                },
                Err(_) => { &&& pre@.is_full() &&& post2@ == pre@ },
            })
            && result1 is Ok
            && result2 is Ok
            && result1 == result2
        )
        ==> post1@ == post2@
{
}

// SET R1: same branch?
proof fn det_set_r1_branch(
    pre: Bitmap, index: usize,
    post1: Bitmap, post2: Bitmap,
    result1: Result<(), Error>, result2: Result<(), Error>,
)
    requires pre.inv(),
    ensures
        (
            post1.inv()
            && (match result1 {
                Ok(()) => {
                    &&& index < post1@.num_bits
                    &&& post1@.is_bit_set(index as int)
                    &&& !pre@.is_bit_set(index as int)
                    &&& post1@.num_bits == pre@.num_bits
                    &&& forall|i: int| 0 <= i < post1@.num_bits && i != (index as int) ==> post1@.is_bit_set(i) == pre@.is_bit_set(i)
                    &&& post1@.set_bits == pre@.set_bits.insert(index as int)
                    &&& post1@.usage() == pre@.usage() + 1
                },
                Err(_) => { &&& index >= pre@.num_bits || pre@.is_bit_set(index as int) &&& post1@ == pre@ },
            })
            && post2.inv()
            && (match result2 {
                Ok(()) => {
                    &&& index < post2@.num_bits
                    &&& post2@.is_bit_set(index as int)
                    &&& !pre@.is_bit_set(index as int)
                    &&& post2@.num_bits == pre@.num_bits
                    &&& forall|i: int| 0 <= i < post2@.num_bits && i != (index as int) ==> post2@.is_bit_set(i) == pre@.is_bit_set(i)
                    &&& post2@.set_bits == pre@.set_bits.insert(index as int)
                    &&& post2@.usage() == pre@.usage() + 1
                },
                Err(_) => { &&& index >= pre@.num_bits || pre@.is_bit_set(index as int) &&& post2@ == pre@ },
            })
        )
        ==> (result1 is Ok <==> result2 is Ok)
{
}

// SET R2: given both Err, same error code?
proof fn det_set_r2_err_code(
    pre: Bitmap, index: usize,
    post1: Bitmap, post2: Bitmap,
    result1: Result<(), Error>, result2: Result<(), Error>,
)
    requires pre.inv(),
    ensures
        (
            post1.inv()
            && (match result1 {
                Ok(()) => {
                    &&& index < post1@.num_bits
                    &&& post1@.is_bit_set(index as int)
                    &&& !pre@.is_bit_set(index as int)
                    &&& post1@.num_bits == pre@.num_bits
                    &&& forall|i: int| 0 <= i < post1@.num_bits && i != (index as int) ==> post1@.is_bit_set(i) == pre@.is_bit_set(i)
                    &&& post1@.set_bits == pre@.set_bits.insert(index as int)
                    &&& post1@.usage() == pre@.usage() + 1
                },
                Err(_) => { &&& index >= pre@.num_bits || pre@.is_bit_set(index as int) &&& post1@ == pre@ },
            })
            && post2.inv()
            && (match result2 {
                Ok(()) => {
                    &&& index < post2@.num_bits
                    &&& post2@.is_bit_set(index as int)
                    &&& !pre@.is_bit_set(index as int)
                    &&& post2@.num_bits == pre@.num_bits
                    &&& forall|i: int| 0 <= i < post2@.num_bits && i != (index as int) ==> post2@.is_bit_set(i) == pre@.is_bit_set(i)
                    &&& post2@.set_bits == pre@.set_bits.insert(index as int)
                    &&& post2@.usage() == pre@.usage() + 1
                },
                Err(_) => { &&& index >= pre@.num_bits || pre@.is_bit_set(index as int) &&& post2@ == pre@ },
            })
            && result1 is Err
            && result2 is Err
        )
        ==> result1 == result2
{
}
