// ALLOC: Complete binary search to concrete witness

// R1: same branch? → PASS (already known)
// R2: both Ok → same index? → FAIL (already known)

// R3: narrow pre — num_bits == 8, usage == 0 (empty bitmap)
proof fn det_alloc_r3(
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
            && result1 is Ok && result2 is Ok
            // Concrete input
            && pre@.num_bits == 8
            && pre@.usage() == 0
        )
        ==> result1 == result2
{
}

// R4: narrow y1, y2 — index1 == 0, index2 == 1?
proof fn det_alloc_r4(
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
            && result1 is Ok && result2 is Ok
            // Fully concrete
            && pre@.num_bits == 8
            && pre@.usage() == 0
            && result1 == Ok(0usize)
            && result2 == Ok(1usize)
        )
        ==> false  // This should be SAT (not provable) if witness is valid
{
}

// SET: Complete binary search

// R1: same branch? → PASS (already known)
// R2: both Err → same error code? → FAIL (already known)

// R3: narrow input — num_bits == 8, index out of bounds (index == 10)
proof fn det_set_r3(
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
            && result1 is Err && result2 is Err
            // Concrete input
            && pre@.num_bits == 8
            && index == 10  // out of bounds
        )
        ==> result1 == result2
{
}

// R4: narrow y1, y2 error codes
proof fn det_set_r4(
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
            && result1 is Err && result2 is Err
            // Fully concrete
            && pre@.num_bits == 8
            && index == 10
            && result1.unwrap_err().code == ::sys::error::ErrorCode::InvalidArgument
            && result2.unwrap_err().code == ::sys::error::ErrorCode::ResourceBusy
        )
        ==> false
{
}
