class stream_seq extends uvm_sequence #(stream_item);
  `uvm_object_utils(stream_seq)
  function new(string name = "stream_seq");
    super.new(name);
  endfunction
  task body();
    `uvm_do(req)
  endtask
endclass
