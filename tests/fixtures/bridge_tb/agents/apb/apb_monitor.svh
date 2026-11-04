class apb_monitor extends uvm_monitor;
  `uvm_component_utils(apb_monitor)
  virtual apb_if vif;
  uvm_analysis_port #(apb_item) ap;
  covergroup cg_apb @(posedge vif.clk);
    cp_write : coverpoint vif.pwrite;
    cp_addr  : coverpoint vif.paddr[7:0];
    x_wa     : cross cp_write, cp_addr;
  endgroup
  function new(string name, uvm_component parent);
    super.new(name, parent);
    ap = new("ap", this);
  endfunction
  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db#(virtual apb_if)::get(this, "", "vif", vif))
      `uvm_fatal("NOVIF", "apb vif not set")
  endfunction
  task run_phase(uvm_phase phase);
    apb_item t;
    forever begin
      @(vif.mon_cb);
      t = apb_item::type_id::create("t");
      ap.write(t);
    end
  endtask
endclass
