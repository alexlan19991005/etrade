"""E*Trade execution adapter (built on ``pyetrade``).

Safety rules:
- No real order is ever placed unless ``place_market_order`` is called
  with ``live=True``. The default is a dry run: validated, logged, and
  returned with ``"dry_run": True``. There is no accidental-order path.
- ``ETRADE_ENV`` selects ``sandbox`` (default) or ``production``; sandbox
  and production keys are separate.
- Credentials come only from environment variables (or a ``.env`` file
  loaded by the caller — see ``.env.example``). Never hard-coded, never
  committed. OAuth tokens live in memory, or in ``~/.etrade_tokens.json``
  if the caller persists them (outside the repo).

Setup: create a developer account at https://developer.etrade.com, copy
``.env.example`` to ``.env`` and fill in the keys, run the OAuth flow once
(``authenticate_interactive``), and test in the sandbox before ever
setting ``ETRADE_ENV=production``.
"""

import json
import logging
import os
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

TOKEN_FILE = Path.home() / ".etrade_tokens.json"


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    return value.strip() if value else None


class ETradeClient:
    """Thin, safe wrapper around pyetrade.

    Parameters
    ----------
    env: 'sandbox' (default) or 'production'. Read from ETRADE_ENV.
    account_id_key: E*Trade accountIdKey to trade in. If None, the first
        account returned by list_accounts() is used.
    token_file: where OAuth access tokens are cached (outside the repo).
    """

    def __init__(
        self,
        env: str | None = None,
        account_id_key: str | None = None,
        token_file: str | Path | None = None,
    ):
        self.env = (env or _env("ETRADE_ENV") or "sandbox").lower()
        if self.env not in ("sandbox", "production"):
            raise ValueError("ETRADE_ENV must be 'sandbox' or 'production'")
        self.dev = self.env == "sandbox"
        if self.dev:
            self.consumer_key = _env("ETRADE_SANDBOX_KEY")
            self.consumer_secret = _env("ETRADE_SANDBOX_SECRET")
        else:
            self.consumer_key = _env("ETRADE_CONSUMER_KEY")
            self.consumer_secret = _env("ETRADE_CONSUMER_SECRET")
        if not self.consumer_key or not self.consumer_secret:
            raise ValueError(
                f"Missing E*Trade {'sandbox' if self.dev else 'production'} "
                "API keys. Copy .env.example to .env and fill them in."
            )
        self.account_id_key = account_id_key or _env("ETRADE_ACCOUNT_ID_KEY")
        self.token_file = Path(token_file) if token_file else TOKEN_FILE
        self._tokens: dict | None = None
        self._accounts = None
        self._market = None
        self._orders = None

    def authorize(self) -> str:
        """Start OAuth; returns the URL to authorise at. The verification
        code from that page goes to ``complete_authorization``."""
        from pyetrade import ETradeOAuth

        self._oauth = ETradeOAuth(self.consumer_key, self.consumer_secret)
        if self.dev:
            # pyetrade hard-codes the production token endpoints; the
            # sandbox key must be exchanged at the sandbox host instead.
            self._oauth.req_token_url = (
                "https://apisb.etrade.com/oauth/request_token"
            )
            self._oauth.access_token_url = (
                "https://apisb.etrade.com/oauth/access_token"
            )
        # pyetrade returns the authorize URL as a plain string.
        return self._oauth.get_request_token()

    def complete_authorization(self, verifier_code: str) -> dict:
        """Finish OAuth with the verification code; cache access tokens."""
        tokens = self._oauth.get_access_token(verifier_code)
        self._tokens = {
            "oauth_token": tokens["oauth_token"],
            "oauth_token_secret": tokens["oauth_token_secret"],
        }
        self.token_file.write_text(json.dumps(self._tokens))
        os.chmod(self.token_file, 0o600)
        return self._tokens

    def authenticate_interactive(self) -> dict:
        """One-shot interactive OAuth (prints URL, reads code from stdin)."""
        if self.token_file.exists():
            self._tokens = json.loads(self.token_file.read_text())
            return self._tokens
        print("Open this URL and authorise the app:")
        print(self.authorize())
        verifier = input("Paste the verification code: ").strip()
        return self.complete_authorization(verifier)

    def _clients(self):
        if self._tokens is None:
            if self.token_file.exists():
                self._tokens = json.loads(self.token_file.read_text())
            else:
                raise RuntimeError(
                    "Not authenticated. Run authenticate_interactive() first."
                )
        if self._market is None:
            from pyetrade import ETradeAccounts, ETradeMarket, ETradeOrder

            kw = dict(
                client_key=self.consumer_key,
                client_secret=self.consumer_secret,
                resource_owner_key=self._tokens["oauth_token"],
                resource_owner_secret=self._tokens["oauth_token_secret"],
                dev=self.dev,
            )
            self._accounts = ETradeAccounts(**kw)
            self._market = ETradeMarket(**kw)
            self._orders = ETradeOrder(**kw)
        return self._accounts, self._market, self._orders

    def _resolve_account(self) -> str:
        if self.account_id_key:
            return self.account_id_key
        accounts, _, _ = self._clients()
        resp = accounts.list_accounts(resp_format="json")
        items = resp["AccountListResponse"]["Accounts"]["Account"]
        if isinstance(items, dict):
            items = [items]
        self.account_id_key = items[0]["accountIdKey"]
        return self.account_id_key

    def get_quotes(self, symbols: list[str]) -> dict[str, float]:
        """Last-trade price per symbol, e.g. ``{"SPY": 612.34}``."""
        _, market, _ = self._clients()
        resp = market.get_quote(symbols, resp_format="json")
        data = resp["QuoteResponse"]["QuoteData"]
        if isinstance(data, dict):
            data = [data]
        quotes = {}
        for item in data:
            product = item.get("Product", {})
            all_data = item.get("All", {})
            price = all_data.get("lastTrade")
            if price is not None:
                quotes[product.get("symbol")] = float(price)
        return quotes

    def get_account_positions(self) -> list[dict]:
        """Current positions: symbol, quantity, market value, cost basis."""
        accounts, _, _ = self._clients()
        account_id_key = self._resolve_account()
        resp = accounts.get_account_portfolio(
            account_id_key, resp_format="json"
        )
        portfolio = resp["PortfolioResponse"]["AccountPortfolio"]
        positions = portfolio[0].get("Position", []) if portfolio else []
        if isinstance(positions, dict):
            positions = [positions]
        out = []
        for p in positions:
            product = p.get("Product", {})
            out.append(
                {
                    "symbol": product.get("symbol"),
                    "quantity": float(p.get("quantity", 0)),
                    "market_value": float(p.get("marketValue", 0)),
                    "cost_basis": float(p.get("totalCost", 0)),
                }
            )
        return out

    def place_market_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        live: bool = False,
    ) -> dict:
        """Place a market order for ``qty`` shares of ``symbol`` ("BUY" or
        "SELL"). ``live=False`` (default) sends nothing: the order is
        validated and returned as a dry-run record. Pass ``live=True`` only
        for a real order, and only after sandbox testing."""
        side = side.upper()
        if side not in ("BUY", "SELL"):
            raise ValueError('side must be "BUY" or "SELL"')
        if qty <= 0:
            raise ValueError("qty must be positive")
        order = {
            "symbol": symbol,
            "quantity": float(qty),
            "orderAction": side,
            "priceType": "MARKET",
            "orderTerm": "GOOD_FOR_DAY",
            "marketSession": "REGULAR",
            "env": self.env,
            "clientOrderId": str(uuid.uuid4()),
        }
        if not live:
            logger.info("[DRY RUN] would place order: %s", order)
            return {"dry_run": True, **order}
        _, _, orders = self._clients()
        account_id_key = self._resolve_account()
        preview = orders.preview_equity_order(
            accountIdKey=account_id_key, **order
        )
        preview_ids = preview["PreviewOrderResponse"]["PreviewIds"]
        preview_id = (
            preview_ids["previewId"]
            if isinstance(preview_ids, dict)
            else preview_ids[0]["previewId"]
        )
        placed = orders.place_equity_order(
            accountIdKey=account_id_key, previewId=preview_id, **order
        )
        logger.info("Placed live order: %s -> %s", order, placed)
        return {"dry_run": False, "order": order, "response": placed}
