use anchor_lang::prelude::*;

#[error_code]
pub enum RawlError {
    #[msg("Unauthorized: only the platform authority can perform this action")]
    Unauthorized,

    #[msg("Unauthorized: only the oracle can perform this action")]
    OracleUnauthorized,

    #[msg("Match is not in the expected status")]
    InvalidMatchStatus,

    #[msg("Match is not open for betting")]
    MatchNotOpen,

    #[msg("Match is not locked")]
    MatchNotLocked,

    #[msg("Match is not resolved")]
    MatchNotResolved,

    #[msg("Match is not cancelled")]
    MatchNotCancelled,

    #[msg("Bet amount must be greater than zero")]
    ZeroBetAmount,

    #[msg("Bet is on the losing side")]
    BetOnLosingSide,

    #[msg("Bet has already been claimed")]
    AlreadyClaimed,

    #[msg("Match timeout has not elapsed")]
    TimeoutNotElapsed,

    #[msg("Claim window has not elapsed")]
    ClaimWindowNotElapsed,

    #[msg("Arithmetic overflow")]
    Overflow,

    #[msg("Invalid fee basis points")]
    InvalidFeeBps,

    #[msg("Invalid side")]
    InvalidSide,

    #[msg("Platform is paused")]
    PlatformPaused,

    #[msg("Bet count not zero")]
    BetCountNotZero,

    #[msg("Winning bet count not zero for fee withdrawal")]
    WinningBetCountNotZero,

    #[msg("Bet amount is below the minimum")]
    BetBelowMinimum,

    #[msg("Betting window has closed")]
    BettingWindowClosed,

    #[msg("Fees have already been withdrawn for this match")]
    FeesAlreadyWithdrawn,

    #[msg("Vault has insufficient balance for this operation")]
    InsufficientVault,

    #[msg("Match timeout must be positive")]
    InvalidTimeout,

    #[msg("Betting window must not be negative")]
    InvalidBettingWindow,
}
