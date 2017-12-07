module our(input clock);

   reg [31:0] x /*verilator public*/;
   reg [31:0] y /*verilator public*/;

   always @(posedge clock) begin
      x <= y;
      y <= x + 1;
   end

  initial begin
    $display("Hello World");
  end
endmodule
