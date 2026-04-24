// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_from_raw_parts_equal(r1: Result<Slab, Error>, r2: Result<Slab, Error>) -> bool {
    (((r1 is Ok) == (r2 is Ok)) && ((r1 is Ok) ==> ((r1->Ok_0)@ == (r2->Ok_0)@)))
}

proof fn det_from_raw_parts(addr: *mut u8, len: usize, block_size: usize, r1: Result<Slab, Error>, r2: Result<Slab, Error>)
    ensures
        ({
            &&& (match r1 {
                 Ok(slab) => {
                     &&& slab.inv()
                     &&& slab@.block_size == block_size
                     &&& slab@.start_addr >= addr as usize
                     &&& slab@.end_addr <= addr as usize + len
                     &&& slab@.allocated_addrs == Set::<usize>::empty()
                 },
                 Err(e) => {
                     &&& e.code == ErrorCode::InvalidArgument
                     &&& {
                         ||| addr as usize == 0
                         ||| len == 0
                         ||| len >= i32::MAX
                         ||| len > isize::MAX
                         ||| addr as usize + len > usize::MAX
                         ||| block_size == 0
                         ||| block_size >= i32::MAX
                         ||| block_size > (usize::MAX - 1) / (u8::BITS as int)
                         ||| len < block_size * 2
                         ||| addr as usize % block_size != 0
                     }
                 }
             })
            &&& (match r2 {
                 Ok(slab) => {
                     &&& slab.inv()
                     &&& slab@.block_size == block_size
                     &&& slab@.start_addr >= addr as usize
                     &&& slab@.end_addr <= addr as usize + len
                     &&& slab@.allocated_addrs == Set::<usize>::empty()
                 },
                 Err(e) => {
                     &&& e.code == ErrorCode::InvalidArgument
                     &&& {
                         ||| addr as usize == 0
                         ||| len == 0
                         ||| len >= i32::MAX
                         ||| len > isize::MAX
                         ||| addr as usize + len > usize::MAX
                         ||| block_size == 0
                         ||| block_size >= i32::MAX
                         ||| block_size > (usize::MAX - 1) / (u8::BITS as int)
                         ||| len < block_size * 2
                         ||| addr as usize % block_size != 0
                     }
                 }
             })
        }) ==> det_from_raw_parts_equal(r1, r2),
{
}