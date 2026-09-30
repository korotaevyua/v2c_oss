// A4: .SUBCKT pins follow the module's port list -- not the order of the
// input/output/inout declarations, and not alphabetical order.
module top (y, VSS, b, VDD, a);
  input a;
  input b;
  output y;
  inout VDD;
  inout VSS;

  NAND2 u0 (.A(a), .B(b), .Y(y), .VDD(VDD), .VSS(VSS));
endmodule
