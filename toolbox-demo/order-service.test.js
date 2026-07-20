import { calculateRefund, getOrderForUser } from "./order-service.js";

describe("order service", () => {
  it("returns an order", async () => {
    const order = { id: "order-7", userId: "user-a", total: 48 };
    const db = { orders: { findById: async () => order } };

    await expect(getOrderForUser(db, order.id, order.userId)).resolves.toEqual(order);
  });

  it("does not expose another user's order", async () => {
    const order = { id: "order-7", userId: "user-a", total: 48 };
    const db = { orders: { findById: async () => order } };

    await expect(getOrderForUser(db, order.id, "user-b")).rejects.toThrow("Order not found");
  });

  it("calculates a refund", () => {
    expect(calculateRefund([{ price: 12, quantity: 2 }])).toBe(24);
  });

  it("rejects negative refund values", () => {
    expect(() => calculateRefund([{ price: 12, quantity: -1 }])).toThrow(
      "Refund items cannot contain negative values",
    );
  });
});
