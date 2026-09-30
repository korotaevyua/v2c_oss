// A2: several instances of the same cell. Each keeps its own name and its own
// nets; nothing resolved for one instance leaks into the next, including when
// they write their connections in different orders.
module top (a, y, VDD, VSS);
  input a;
  output y;
  inout VDD, VSS;
  wire n1, n2, n3;

  INV u1 (.A(a), .Y(n1), .VDD(VDD), .VSS(VSS));
  INV u2 (.VSS(VSS), .VDD(VDD), .Y(n2), .A(n1));
  INV u3 (.A(n2), .Y(n3), .VDD(VDD), .VSS(VSS));
  INV u4 (.Y(y), .A(n3), .VSS(VSS), .VDD(VDD));
endmodule
