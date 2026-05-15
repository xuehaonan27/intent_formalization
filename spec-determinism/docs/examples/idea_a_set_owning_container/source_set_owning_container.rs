
	#[verifier::external_body]
    #[verifier(external_body)]
    pub fn set_owning_container(&mut self, index: usize, owning_container_op: Option<ContainerPtr>)
        requires
            old(self).page_array.wf(),
            0 <= index < NUM_PAGES,
        ensures
            self.page_array.wf(),
            forall|i: int|
                #![trigger self.page_array@[i]]
                #![trigger old(self).page_array@[i]]
                0 <= i < NUM_PAGES && i != index ==> self.page_array@[i] =~= old(
                    self,
                ).page_array@[i],
            self.page_array@[index as int].addr =~= old(self).page_array@[index as int].addr,
            self.page_array@[index as int].state =~= old(self).page_array@[index as int].state,
            self.page_array@[index as int].is_io_page =~= old(
                self,
            ).page_array@[index as int].is_io_page,
            self.page_array@[index as int].rev_pointer =~= old(
                self,
            ).page_array@[index as int].rev_pointer,
            self.page_array@[index as int].ref_count =~= old(
                self,
            ).page_array@[index as int].ref_count,
            // self.page_array@[index as int].owning_container =~= old(self).page_array@[index as int].owning_container,
            self.page_array@[index as int].owning_container =~= owning_container_op,
            self.page_array@[index as int].mappings =~= old(
                self,
            ).page_array@[index as int].mappings,
            self.page_array@[index as int].io_mappings =~= old(
                self,
            ).page_array@[index as int].io_mappings,
            self.free_pages_4k == old(self).free_pages_4k,
            self.free_pages_2m == old(self).free_pages_2m,
            self.free_pages_1g == old(self).free_pages_1g,
            self.allocated_pages_4k == old(self).allocated_pages_4k,
            self.allocated_pages_2m == old(self).allocated_pages_2m,
            self.allocated_pages_1g == old(self).allocated_pages_1g,
            self.mapped_pages_4k == old(self).mapped_pages_4k,
            self.mapped_pages_2m == old(self).mapped_pages_2m,
            self.mapped_pages_1g == old(self).mapped_pages_1g,
            self.page_perms_4k == old(self).page_perms_4k,
            self.page_perms_2m == old(self).page_perms_2m,
            self.page_perms_1g == old(self).page_perms_1g,
            self.container_map_4k == old(self).container_map_4k,
            self.container_map_2m == old(self).container_map_2m,
            self.container_map_1g == old(self).container_map_1g,
	{
		unimplemented!()
	}

}
