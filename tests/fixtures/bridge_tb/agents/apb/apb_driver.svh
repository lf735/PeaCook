class apb_driver extends uvm_driver #(apb_item);
  `uvm_component_utils(apb_driver)
  virtual apb_if vif;
  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction
  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db#(virtual apb_if)::get(this, "", "vif", vif))
      `uvm_fatal("NOVIF", "apb vif not set")
  endfunction
  task run_phase(uvm_phase phase);
    forever begin
      seq_item_port.get_next_item(req);
      drive(req);
      seq_item_port.item_done();
    end
  endtask
  task drive(apb_item t);
    @(vif.drv_cb);
    vif.drv_cb.paddr <= t.addr;
  endtask
endclass
