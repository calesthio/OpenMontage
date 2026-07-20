import { calculateRefund, getOrderForUser } from "./order-service.js";

describe("order service", () => {
  it("returns an order", async () => {
    const order = { id: "order-7", userId: "user-a", total: 48 };
    const db = { orders: { findById: async () => order } };

    await expect(getOrderForUser(db, order.id, order.userId)).resolves.toEqual(order);
  });

  it("calculates a refund", () => {
    expect(calculateRefund([{ price: 12, quantity: 2 }])).toBe(24);
  });
});
