// A3: hierarchy. Each module becomes its own .SUBCKT, and an instance of a
// module is resolved against that module's port list, like any library cell.
module and2 (a, b, y, VDD, VSS);
  input a, b;
  output y;
  inout VDD, VSS;
  wire n;

  NAND2 g0 (.A(a), .B(b), .Y(n), .VDD(VDD), .VSS(VSS));
  INV g1 (.A(n), .Y(y), .VDD(VDD), .VSS(VSS));
endmodule

module top (a, b, c, y, VDD, VSS);
  input a, b, c;
  output y;
  inout VDD, VSS;
  wire ab;

  and2 u_and0 (.VSS(VSS), .VDD(VDD), .y(ab), .b(b), .a(a));
  and2 u_and1 (.a(ab), .b(c), .y(y), .VDD(VDD), .VSS(VSS));
endmodule
