class apb_agent extends uvm_agent;
  `uvm_component_utils(apb_agent)
  apb_cfg       cfg;
  apb_driver    drv;
  apb_sequencer sqr;
  apb_monitor   mon;
  uvm_analysis_port #(apb_item) ap;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db#(apb_cfg)::get(this, "", "cfg", cfg))
      `uvm_fatal("NOCFG", "apb_cfg not set")
    mon = apb_monitor::type_id::create("mon", this);
    ap  = new("ap", this);
    if (cfg.is_active == UVM_ACTIVE) begin
      drv = apb_driver::type_id::create("drv", this);
      sqr = apb_sequencer::type_id::create("sqr", this);
    end
  endfunction

  function void connect_phase(uvm_phase phase);
    if (cfg.is_active == UVM_ACTIVE)
      drv.seq_item_port.connect(sqr.seq_item_export);
    mon.ap.connect(ap);
  endfunction
endclass
