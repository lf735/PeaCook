class apb_base_seq extends uvm_sequence #(apb_item);
  `uvm_object_utils(apb_base_seq)
  function new(string name = "apb_base_seq");
    super.new(name);
  endfunction
endclass

class apb_cfg_seq extends apb_base_seq;
  `uvm_object_utils(apb_cfg_seq)
  rand int unsigned n_writes = 4;
  function new(string name = "apb_cfg_seq");
    super.new(name);
  endfunction
  task body();
    repeat (n_writes) begin
      `uvm_do_with(req, { write == 1; })
    end
  endtask
endclass
