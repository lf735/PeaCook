class stream_driver extends uvm_driver #(stream_item);
  `uvm_component_utils(stream_driver)
  virtual stream_if vif;
  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction
  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db#(virtual stream_if)::get(this, "", "vif", vif))
      `uvm_fatal("NOVIF", "stream vif not set")
  endfunction
  task run_phase(uvm_phase phase);
    forever begin
      seq_item_port.get_next_item(req);
      seq_item_port.item_done();
    end
  endtask
endclass

class stream_err_driver extends stream_driver;
  `uvm_component_utils(stream_err_driver)
  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction
endclass

class stream_monitor extends uvm_monitor;
  `uvm_component_utils(stream_monitor)
  virtual stream_if vif;
  uvm_analysis_port #(stream_item) ap;
  function new(string name, uvm_component parent);
    super.new(name, parent);
    ap = new("ap", this);
  endfunction
  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db#(virtual stream_if)::get(this, "", "vif", vif))
      `uvm_fatal("NOVIF", "stream vif not set")
  endfunction
endclass
