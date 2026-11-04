package bridge_tests_pkg;
  import uvm_pkg::*;
  `include "uvm_macros.svh"
  import apb_pkg::*;
  import stream_pkg::*;
  import bridge_env_pkg::*;

  class bridge_base_test extends uvm_test;
    `uvm_component_utils(bridge_base_test)
    bridge_env     env;
    bridge_env_cfg env_cfg;
    apb_cfg        apb_c;

    function new(string name, uvm_component parent);
      super.new(name, parent);
    endfunction

    function void build_phase(uvm_phase phase);
      super.build_phase(phase);
      env_cfg = bridge_env_cfg::type_id::create("env_cfg");
      apb_c   = apb_cfg::type_id::create("apb_c");
      apb_c.is_active = UVM_ACTIVE;
      env_cfg.apb     = apb_c;
      uvm_config_db#(bridge_env_cfg)::set(this, "env", "cfg", env_cfg);
      uvm_config_db#(apb_cfg)::set(this, "env.apb_agt", "cfg", apb_c);
      env = bridge_env::type_id::create("env", this);
    endfunction
  endclass

  class bridge_smoke_test extends bridge_base_test;
    `uvm_component_utils(bridge_smoke_test)
    function new(string name, uvm_component parent);
      super.new(name, parent);
    endfunction
    task run_phase(uvm_phase phase);
      bridge_smoke_vseq vseq;
      phase.raise_objection(this);
      vseq = bridge_smoke_vseq::type_id::create("vseq");
      vseq.start(env.vseqr);
      phase.drop_objection(this);
    endtask
  endclass

  // Remplace le driver de l'agent d'entrée par une version qui injecte des erreurs
  class bridge_err_test extends bridge_smoke_test;
    `uvm_component_utils(bridge_err_test)
    function new(string name, uvm_component parent);
      super.new(name, parent);
    endfunction
    function void build_phase(uvm_phase phase);
      set_inst_override_by_type("env.in_agt.drv", stream_driver::get_type(), stream_err_driver::get_type());
      super.build_phase(phase);
    endfunction
  endclass

  // 4 agents de sortie au lieu de 2
  class bridge_multi_out_test extends bridge_smoke_test;
    `uvm_component_utils(bridge_multi_out_test)
    function new(string name, uvm_component parent);
      super.new(name, parent);
    endfunction
    function void build_phase(uvm_phase phase);
      super.build_phase(phase);
      env_cfg.num_out = 4;
    endfunction
  endclass

  // Agent APB passif, sans modèle de référence ni couverture
  class bridge_passive_test extends bridge_smoke_test;
    `uvm_component_utils(bridge_passive_test)
    function new(string name, uvm_component parent);
      super.new(name, parent);
    endfunction
    function void build_phase(uvm_phase phase);
      super.build_phase(phase);
      apb_c.is_active       = UVM_PASSIVE;
      env_cfg.has_ref_model = 0;
      env_cfg.enable_cov    = 0;
    endfunction
  endclass
endpackage
