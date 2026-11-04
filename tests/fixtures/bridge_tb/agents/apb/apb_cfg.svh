class apb_cfg extends uvm_object;
  uvm_active_passive_enum is_active = UVM_ACTIVE;
  bit has_coverage = 1;
  `uvm_object_utils(apb_cfg)
  function new(string name = "apb_cfg");
    super.new(name);
  endfunction
endclass
