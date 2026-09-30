// A1: one instance of one cell -- the minimal end-to-end path.
module top (a, y, VDD, VSS);
  input a;
  output y;
  inout VDD;
  inout VSS;

  INV u0 (.A(a), .Y(y), .VDD(VDD), .VSS(VSS));
endmodule
