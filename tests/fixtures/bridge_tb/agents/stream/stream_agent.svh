class stream_agent extends uvm_agent;
  `uvm_component_utils(stream_agent)
  stream_driver    drv;
  stream_sequencer sqr;
  stream_monitor   mon;
  uvm_analysis_port #(stream_item) ap;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    mon = stream_monitor::type_id::create("mon", this);
    ap  = new("ap", this);
    if (get_is_active() == UVM_ACTIVE) begin
      drv = stream_driver::type_id::create("drv", this);
      sqr = stream_sequencer::type_id::create("sqr", this);
    end
  endfunction

  function void connect_phase(uvm_phase phase);
    if (get_is_active() == UVM_ACTIVE)
      drv.seq_item_port.connect(sqr.seq_item_export);
    mon.ap.connect(ap);
  endfunction
endclass
