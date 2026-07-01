import re

class PIIRedactor:
    """
    Utility to redact PII (Personal Identifiable Information) such as routing numbers,
    account numbers, credit cards, and social security numbers from ledger data or query strings.
    """
    
    # Matches social security numbers (e.g. 000-00-0000)
    SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    
    # Matches common credit card shapes (13 to 16 digits with potential spaces/dashes)
    CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
    
    # Matches American routing transit numbers (exactly 9 digits)
    ROUTING_NUMBER_PATTERN = re.compile(r"\b\d{9}\b")
    
    # Matches potential account numbers (long strings of digits between 10 and 17 digits)
    ACCOUNT_NUMBER_PATTERN = re.compile(r"\b\d{10,17}\b")

    @classmethod
    def redact_text(cls, text: str) -> str:
        if not text or not isinstance(text, str):
            return text
        
        # Redact SSN
        text = cls.SSN_PATTERN.sub("[SSN_REDACTED]", text)
        
        # Redact Credit Cards
        text = cls.CREDIT_CARD_PATTERN.sub("[CREDIT_CARD_REDACTED]", text)
        
        # Redact Routing Numbers
        # Ensure we don't accidentally redact standard dates or small numbers
        text = cls.ROUTING_NUMBER_PATTERN.sub("[ROUTING_REDACTED]", text)
        
        # Redact Account Numbers
        text = cls.ACCOUNT_NUMBER_PATTERN.sub("[ACCOUNT_REDACTED]", text)
        
        return text

    @classmethod
    def redact_transaction(cls, transaction: dict) -> dict:
        """
        Redacts description fields in a transaction dict.
        """
        redacted = transaction.copy()
        if "description" in redacted:
            redacted["description"] = cls.redact_text(redacted["description"])
        return redacted

    @classmethod
    def redact_account(cls, account: dict) -> dict:
        """
        Redacts sensitive fields in an account dict.
        """
        redacted = account.copy()
        if "routing_number" in redacted:
            redacted["routing_number"] = "[ROUTING_REDACTED]"
        if "account_number" in redacted:
            # Mask all but the last 4 digits
            acc_num = str(redacted["account_number"])
            if len(acc_num) > 4:
                redacted["account_number"] = "*" * (len(acc_num) - 4) + acc_num[-4:]
            else:
                redacted["account_number"] = "[ACCOUNT_REDACTED]"
        return redacted

if __name__ == "__main__":
    sample_text = "My routing number is 121000248 and my card is 4111-1111-1111-1111. SSN is 000-12-3456."
    print("Original:", sample_text)
    print("Redacted:", PIIRedactor.redact_text(sample_text))
