// B10: a library given with -lsp is read for pin order only. The macro
// resolves against it, but only the -s library is .INCLUDEd in the output.
module top (a, y, VDD, VSS);
  input a;
  output y;
  inout VDD, VSS;
  wire a_n;

  INV u_inv (.A(a), .Y(a_n), .VDD(VDD), .VSS(VSS));
  HARDMACRO u_macro (.VSS(VSS), .VDD(VDD), .DI(a_n), .EN(a), .CLK(a), .DO(y));
endmodule
