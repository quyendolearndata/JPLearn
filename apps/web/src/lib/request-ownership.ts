export type AuthIdentity = Readonly<{
  token: string;
  userId: string;
}>;

export type RequestTicket = Readonly<{
  authEpoch: number;
  generation: number;
  identity: AuthIdentity;
  scope: string;
}>;

function sameIdentity(left: AuthIdentity, right: AuthIdentity): boolean {
  return left.token === right.token && left.userId === right.userId;
}

/**
 * Makes asynchronous UI work explicitly belong to one auth epoch and one
 * operation scope. Aborting a request can save work, but this gate remains the
 * authority before any response is allowed to update React state.
 */
export class RequestOwnershipGate {
  private authEpoch = 0;
  private mounted = true;
  private readonly generations = new Map<string, number>();

  next(scope: string, identity: AuthIdentity): RequestTicket {
    const generation = (this.generations.get(scope) ?? 0) + 1;
    this.generations.set(scope, generation);
    return { authEpoch: this.authEpoch, generation, identity, scope };
  }

  isCurrent(ticket: RequestTicket, identity: AuthIdentity | null): boolean {
    return Boolean(
      this.mounted
      && identity
      && ticket.authEpoch === this.authEpoch
      && ticket.generation === this.generations.get(ticket.scope)
      && sameIdentity(ticket.identity, identity),
    );
  }

  invalidateScope(scope: string): void {
    this.generations.set(scope, (this.generations.get(scope) ?? 0) + 1);
  }

  changeAuthEpoch(): void {
    this.authEpoch += 1;
    this.generations.clear();
  }

  activate(): void {
    this.mounted = true;
    this.changeAuthEpoch();
  }

  dispose(): void {
    this.mounted = false;
    this.changeAuthEpoch();
  }
}
