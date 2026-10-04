// B9: the library given with -s is nothing but a list of .INCLUDE lines.
// Cells are found through the includes; the output .INCLUDEs the list file
// only, and the comparator follows the rest itself.
module top (clk, en, d, q, VDD, VSS);
  input clk, en, d;
  output q;
  inout VDD, VSS;
  wire en_n, dout;

  INV u_inv (.A(en), .Y(en_n), .VDD(VDD), .VSS(VSS));
  HARDMACRO u_macro (.DI(d), .EN(en_n), .CLK(clk), .DO(dout), .VSS(VSS), .VDD(VDD));
  NAND2 u_out (.A(dout), .B(en), .Y(q), .VDD(VDD), .VSS(VSS));
endmodule
