class bridge_env_cfg extends uvm_object;
  int unsigned num_out       = 2;
  bit          has_ref_model = 1;
  bit          enable_cov    = 1;
  apb_cfg      apb;
  `uvm_object_utils(bridge_env_cfg)
  function new(string name = "bridge_env_cfg");
    super.new(name);
  endfunction
endclass
