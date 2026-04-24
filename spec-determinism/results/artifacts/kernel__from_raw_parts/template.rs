// Generated equal-fn for determinism check.
// Policy: errs_equivalent=True, opaque_ok=False
spec fn det_from_raw_parts_equal(r1: Result<Kheap, Error>, r2: Result<Kheap, Error>) -> bool {
    (((r1 is Ok) == (r2 is Ok)) && ((r1 is Ok) ==> ((r1->Ok_0)@ == (r2->Ok_0)@)))
}

proof fn det_from_raw_parts(addr: usize, size: usize, r1: Result<Kheap, Error>, r2: Result<Kheap, Error>)
    requires (addr as int + size as int <= usize::MAX as int), (size as int <= isize::MAX as int),
    ensures
        ({
            &&& (match r1 {
                Ok(heap) => {
                    let slab_size = size as int / NUM_OF_SLABS as int;
                    // FN-2b: heap invariant holds
                    &&& heap.inv()
                    // FN-2c: all slabs start fully unallocated
                    &&& forall|i: int| 0 <= i < NUM_OF_SLABS as int ==>
                        (#[trigger] heap@.slabs[i]).allocated_addrs == Set::<usize>::empty()
                    // FN-2e: each slab is contained within its partition
                    &&& forall|i: int| 0 <= i < NUM_OF_SLABS as int ==> {
                        &&& (#[trigger] heap@.slabs[i]).start_addr >= addr as int + i * slab_size
                        &&& heap@.slabs[i].end_addr <= addr as int + (i + 1) * slab_size
                    }
                    // FN-2g (forward): success implies preconditions held
                    &&& addr as int % PAGE_SIZE as int == 0
                    &&& size >= MIN_HEAP_SIZE
                    &&& size as int % MIN_HEAP_SIZE as int == 0
                }
                Err(e) => {
                    // FN-2f: error code
                    &&& e.code == ErrorCode::InvalidArgument
                }
            })
            &&& (match r2 {
                Ok(heap) => {
                    let slab_size = size as int / NUM_OF_SLABS as int;
                    // FN-2b: heap invariant holds
                    &&& heap.inv()
                    // FN-2c: all slabs start fully unallocated
                    &&& forall|i: int| 0 <= i < NUM_OF_SLABS as int ==>
                        (#[trigger] heap@.slabs[i]).allocated_addrs == Set::<usize>::empty()
                    // FN-2e: each slab is contained within its partition
                    &&& forall|i: int| 0 <= i < NUM_OF_SLABS as int ==> {
                        &&& (#[trigger] heap@.slabs[i]).start_addr >= addr as int + i * slab_size
                        &&& heap@.slabs[i].end_addr <= addr as int + (i + 1) * slab_size
                    }
                    // FN-2g (forward): success implies preconditions held
                    &&& addr as int % PAGE_SIZE as int == 0
                    &&& size >= MIN_HEAP_SIZE
                    &&& size as int % MIN_HEAP_SIZE as int == 0
                }
                Err(e) => {
                    // FN-2f: error code
                    &&& e.code == ErrorCode::InvalidArgument
                }
            })
        }) ==> det_from_raw_parts_equal(r1, r2),
{
}