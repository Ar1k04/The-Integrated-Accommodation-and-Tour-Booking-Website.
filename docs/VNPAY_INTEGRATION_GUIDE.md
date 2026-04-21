# VNPay Integration Guide for Booking Platform

---

## Your VNPay Credentials

From your registration email:

```env
# Add to .env file
VNPAY_TMN_CODE=JVNWOIL0
VNPAY_HASH_SECRET=UKQ5BZ0MYX20ODFTZ8JGFE7F4DO3WGDE
VNPAY_PAYMENT_URL=https://sandbox.vnpayment.vn/paymentv2/vpcpay.html
VNPAY_API_URL=https://sandbox.vnpayment.vn/merchant_webapi/merchant_transaction
```

---

## Overview

VNPay flow for your booking platform:

```
1. User completes booking (room/tour/flight)
2. Backend creates PaymentURL with HMAC-SHA512 checksum
3. Redirect user to VNPay payment page
4. User pays (ATM, QR, Credit Card, etc.)
5. VNPay redirects back to your website (Return URL)
6. VNPay sends IPN callback (server-to-server)
7. Verify IPN and update booking status
```

---

## Step 1: Setup Dependencies

```bash
pip install requests python-dotenv hmac hashlib
```

---

## Step 2: Create VNPay Service Class

Create `backend/services/vnpay_service.py`:

```python
import os
import hashlib
import hmac
import json
import logging
from typing import Dict, Optional
from datetime import datetime
from urllib.parse import urlencode
import httpx

logger = logging.getLogger(__name__)

class VNPayService:
    """VNPay payment gateway integration"""
    
    def __init__(self):
        self.tmn_code = os.getenv("VNPAY_TMN_CODE", "JVNWOIL0")
        self.hash_secret = os.getenv("VNPAY_HASH_SECRET", "UKQ5BZ0MYX20ODFTZ8JGFE7F4DO3WGDE")
        self.payment_url = os.getenv("VNPAY_PAYMENT_URL", 
                                     "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html")
        self.api_url = os.getenv("VNPAY_API_URL",
                                "https://sandbox.vnpayment.vn/merchant_webapi/merchant_transaction")
    
    def _create_hmac_sha512(self, data: str) -> str:
        """Create HMAC-SHA512 checksum"""
        return hmac.new(
            self.hash_secret.encode(),
            data.encode(),
            hashlib.sha512
        ).hexdigest().upper()
    
    def _sort_dict(self, data: Dict) -> Dict:
        """Sort dictionary keys alphabetically (required by VNPay)"""
        return dict(sorted(data.items()))
    
    def create_payment_url(
        self,
        booking_id: str,
        amount: int,  # VND (smallest unit)
        customer_email: str,
        customer_phone: str,
        customer_name: str,
        return_url: str,
        description: str = "Booking Payment",
    ) -> str:
        """
        Create VNPay payment URL
        
        Args:
            booking_id: Your booking ID (will be passed back in response)
            amount: Amount in VND (must be > 0)
            customer_email: Customer email for receipt
            customer_phone: Customer phone number
            customer_name: Customer full name
            return_url: URL to redirect after payment (must be HTTPS and accessible)
            description: Payment description
        
        Returns:
            Full VNPay payment URL for redirect
        
        Example:
            payment_url = service.create_payment_url(
                booking_id="BOOKING_12345",
                amount=500000,  # 500,000 VND
                customer_email="user@example.com",
                customer_phone="0123456789",
                customer_name="Nguyen Van A",
                return_url="https://yourdomain.com/payment/callback",
                description="Book Hotel Room"
            )
            # Redirect user to payment_url
        """
        # Generate unique transaction ID (TmnCode + timestamp + booking_id)
        vnp_transaction_no = f"{self.tmn_code}{int(datetime.now().timestamp())}"
        
        # Build payment request data
        vnp_params = {
            "vnp_Version": "2.1.0",
            "vnp_Command": "pay",
            "vnp_TmnCode": self.tmn_code,
            "vnp_Locale": "vn",
            "vnp_CurrCode": "VND",
            "vnp_TxnRef": str(booking_id),  # Your booking ID
            "vnp_OrderInfo": description,
            "vnp_OrderType": "other",
            "vnp_Amount": str(amount * 100),  # VNPay requires: amount * 100
            "vnp_ReturnUrl": return_url,
            "vnp_IpAddr": "127.0.0.1",  # Will be overridden by FastAPI request IP
            "vnp_CreateDate": datetime.now().strftime("%Y%m%d%H%M%S"),
            "vnp_ExpireDate": datetime.now().strftime("%Y%m%d%H%M%S"),  # Optional
            "vnp_Bill_Mobile": customer_phone,
            "vnp_Bill_Email": customer_email,
            "vnp_Bill_FirstName": customer_name.split()[0] if customer_name else "",
            "vnp_Bill_LastName": " ".join(customer_name.split()[1:]) if customer_name else "",
        }
        
        # Sort and create checksum
        sorted_params = self._sort_dict(vnp_params)
        data_for_checksum = "&".join([f"{k}={v}" for k, v in sorted_params.items()])
        vnp_secure_hash = self._create_hmac_sha512(data_for_checksum)
        
        # Add checksum to params
        sorted_params["vnp_SecureHash"] = vnp_secure_hash
        
        # Build final URL
        payment_url = f"{self.payment_url}?{urlencode(sorted_params)}"
        
        logger.info(f"Created VNPay URL for booking {booking_id}: {amount} VND")
        return payment_url
    
    def verify_ipn_callback(self, vnp_params: Dict[str, str]) -> tuple[bool, Optional[Dict]]:
        """
        Verify IPN callback from VNPay (server-to-server)
        
        Args:
            vnp_params: Dictionary of all vnp_* parameters from VNPay callback
        
        Returns:
            (is_valid, response_code)
            - is_valid: True if signature is valid and payment successful
            - response_code: Parsed response code dict
        
        Example in FastAPI route:
            @router.get("/payment/callback")
            async def payment_callback(request: Request):
                vnp_params = dict(request.query_params)
                is_valid, response = vnpay_service.verify_ipn_callback(vnp_params)
                
                if not is_valid:
                    return {"RspCode": "97", "Message": "Invalid checksum"}
                
                booking_id = response.get("booking_id")
                response_code = response.get("vnp_ResponseCode")
                
                if response_code == "00":
                    # Payment success - update booking status to 'confirmed'
                    await update_booking_payment_success(booking_id)
                    return {"RspCode": "00", "Message": "Success"}
                else:
                    # Payment failed
                    return {"RspCode": "01", "Message": "Payment failed"}
        """
        try:
            # Extract checksum
            vnp_secure_hash = vnp_params.pop("vnp_SecureHash", "")
            vnp_secure_hash_type = vnp_params.pop("vnp_SecureHashType", "SHA512")
            
            # Sort and recreate checksum
            sorted_params = self._sort_dict(vnp_params)
            data_for_checksum = "&".join([f"{k}={v}" for k, v in sorted_params.items()])
            computed_hash = self._create_hmac_sha512(data_for_checksum)
            
            # Verify checksum
            if computed_hash != vnp_secure_hash:
                logger.warning(f"IPN callback checksum mismatch. Computed: {computed_hash}, Received: {vnp_secure_hash}")
                return False, None
            
            # Verify response code
            response_code = vnp_params.get("vnp_ResponseCode", "")
            
            return True, {
                "booking_id": vnp_params.get("vnp_TxnRef"),
                "vnp_ResponseCode": response_code,
                "vnp_TransactionNo": vnp_params.get("vnp_TransactionNo"),
                "vnp_BankCode": vnp_params.get("vnp_BankCode"),
                "vnp_Amount": int(vnp_params.get("vnp_Amount", 0)) / 100,  # Convert back to VND
            }
        
        except Exception as e:
            logger.error(f"Error verifying IPN callback: {str(e)}")
            return False, None
    
    async def query_transaction(self, transaction_no: str, amount: int) -> Dict:
        """
        Query transaction status from VNPay API (optional, for reconciliation)
        
        Args:
            transaction_no: VNPay transaction number from callback
            amount: Amount in VND (must match original transaction)
        
        Returns:
            Transaction details from VNPay
        """
        request_id = f"{self.tmn_code}{int(datetime.now().timestamp())}"
        
        request_data = {
            "TmnCode": self.tmn_code,
            "TransactionNo": transaction_no,
            "OrderInfo": f"Query TXN {transaction_no}",
            "RequestId": request_id,
        }
        
        # Create checksum for API request
        data_for_checksum = f"{request_data['TmnCode']}{request_data['TransactionNo']}{request_data['RequestId']}"
        request_data["SecureHash"] = self._create_hmac_sha512(data_for_checksum)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    json=request_data,
                    timeout=10
                )
                return response.json()
        except Exception as e:
            logger.error(f"Error querying VNPay transaction: {str(e)}")
            return {}
```

---

## Step 3: Add VNPay Router in FastAPI

Create `backend/routers/payments.py`:

```python
from fastapi import APIRouter, HTTPException, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from decimal import Decimal
import logging

from core.database import get_db
from services.vnpay_service import VNPayService
from models import Booking, Payment, BookingItem
from schemas import PaymentRequest, PaymentResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["payments"])

vnpay_service = VNPayService()


@router.post("/create-vnpay-url")
async def create_vnpay_payment(
    payment_req: PaymentRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create VNPay payment URL for a booking
    
    Request:
        {
            "booking_id": "uuid",
            "return_url": "https://yourdomain.com/payment/return"
        }
    """
    try:
        # Fetch booking from DB
        booking = await db.get(Booking, payment_req.booking_id)
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        # Calculate amount in VND
        amount_vnd = int(booking.total_price * 100)  # Assuming total_price is in VND
        
        # Get customer info
        customer = booking.user  # Relationship to User model
        
        # Create VNPay payment URL
        payment_url = vnpay_service.create_payment_url(
            booking_id=str(booking.id),
            amount=amount_vnd,
            customer_email=customer.email,
            customer_phone=customer.phone_number,
            customer_name=customer.full_name,
            return_url=payment_req.return_url,
            description=f"Booking {booking.id}"
        )
        
        return {
            "data": {
                "payment_url": payment_url,
                "booking_id": str(booking.id)
            },
            "message": "VNPay payment URL created successfully",
            "status": "success"
        }
    
    except Exception as e:
        logger.error(f"Error creating VNPay URL: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create payment URL")


@router.get("/vnpay/return")
async def vnpay_return(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    VNPay return URL - User is redirected here after payment
    (NOT the IPN callback - this is just for user redirect)
    """
    vnp_params = dict(request.query_params)
    
    is_valid, response = vnpay_service.verify_ipn_callback(vnp_params)
    
    if not is_valid:
        return {
            "data": None,
            "message": "Invalid payment signature",
            "status": "failed"
        }
    
    booking_id = response.get("booking_id")
    response_code = response.get("vnp_ResponseCode")
    
    # Update booking status based on payment result
    if response_code == "00":
        # Payment successful
        booking = await db.get(Booking, booking_id)
        if booking:
            booking.status = "confirmed"
            # Create Payment record
            payment = Payment(
                booking_id=booking.id,
                amount=response.get("vnp_Amount"),
                currency="VND",
                payment_method="ATM",  # Or get from vnp_params
                provider="vnpay",
                provider_transaction_id=response.get("vnp_TransactionNo"),
                status="success",
            )
            db.add(payment)
            await db.commit()
        
        return {
            "data": {"booking_id": booking_id},
            "message": "Payment successful",
            "status": "success"
        }
    else:
        # Payment failed
        return {
            "data": {"booking_id": booking_id},
            "message": "Payment failed or cancelled",
            "status": "failed"
        }


@router.post("/vnpay/ipn")
async def vnpay_ipn_callback(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    VNPay IPN callback - Server-to-server notification
    IMPORTANT: This must be a PUBLIC HTTPS URL that VNPay can reach
    
    Return codes for VNPay:
    - RspCode: "00" = Success (VNPay will stop retrying)
    - RspCode: "01" = Failure or unknown (VNPay will retry)
    """
    vnp_params = dict(request.query_params)
    
    # Verify signature
    is_valid, response = vnpay_service.verify_ipn_callback(vnp_params)
    
    if not is_valid:
        logger.warning(f"Invalid IPN callback signature")
        return {"RspCode": "97", "Message": "Invalid checksum"}
    
    booking_id = response.get("booking_id")
    response_code = response.get("vnp_ResponseCode")
    amount = response.get("vnp_Amount")
    transaction_no = response.get("vnp_TransactionNo")
    
    try:
        # Fetch booking
        booking = await db.get(Booking, booking_id)
        if not booking:
            logger.error(f"Booking not found: {booking_id}")
            return {"RspCode": "01", "Message": "Booking not found"}
        
        # Verify amount matches
        if int(booking.total_price) != int(amount):
            logger.error(f"Amount mismatch for booking {booking_id}")
            return {"RspCode": "04", "Message": "Amount mismatch"}
        
        # Check if already processed
        existing_payment = await db.execute(
            db.select(Payment).filter(
                Payment.provider_transaction_id == transaction_no
            )
        )
        if existing_payment.scalars().first():
            logger.info(f"Payment already processed: {transaction_no}")
            return {"RspCode": "00", "Message": "Success"}
        
        # Handle payment result
        if response_code == "00":
            # Payment successful
            booking.status = "confirmed"
            payment = Payment(
                booking_id=booking.id,
                amount=amount,
                currency="VND",
                payment_method=vnp_params.get("vnp_BankCode", "ATM"),
                provider="vnpay",
                provider_transaction_id=transaction_no,
                status="success",
            )
            db.add(payment)
            
            # Award loyalty points (if applicable)
            points_earned = int(amount / 1000)  # Example: 1 point per 1000 VND
            if booking.user and points_earned > 0:
                booking.user.total_points += points_earned
                from models import LoyaltyTransaction
                loyalty_txn = LoyaltyTransaction(
                    user_id=booking.user.id,
                    booking_id=booking.id,
                    points=points_earned,
                    type="earn",
                    description=f"Points earned from booking {booking_id}"
                )
                db.add(loyalty_txn)
            
            await db.commit()
            logger.info(f"Payment successful for booking {booking_id}")
            return {"RspCode": "00", "Message": "Success"}
        
        else:
            # Payment failed
            booking.status = "cancelled"
            payment = Payment(
                booking_id=booking.id,
                amount=amount,
                currency="VND",
                provider="vnpay",
                provider_transaction_id=transaction_no,
                status="failed",
            )
            db.add(payment)
            await db.commit()
            logger.warning(f"Payment failed for booking {booking_id}, code: {response_code}")
            return {"RspCode": "01", "Message": "Payment failed"}
    
    except Exception as e:
        logger.error(f"Error processing IPN callback: {str(e)}")
        return {"RspCode": "01", "Message": "Processing error"}
```

---

## Step 4: Add Pydantic Schemas

Add to `backend/schemas.py`:

```python
from pydantic import BaseModel, EmailStr
from typing import Optional

class PaymentRequest(BaseModel):
    """Request to create payment"""
    booking_id: str
    return_url: str  # https://yourdomain.com/payment/return

class PaymentResponse(BaseModel):
    """Payment creation response"""
    payment_url: str
    booking_id: str
```

---

## Step 5: Frontend Integration (React)

Create `frontend/src/services/paymentService.js`:

```javascript
import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

export const paymentService = {
  /**
   * Create VNPay payment URL
   * @param {string} bookingId
   * @returns {Promise<string>} Payment URL for redirect
   */
  async createVNPayPayment(bookingId) {
    try {
      const response = await axios.post(`${API_BASE}/payments/create-vnpay-url`, {
        booking_id: bookingId,
        return_url: `${window.location.origin}/payment/return`
      });
      
      if (response.data.status === 'success') {
        return response.data.data.payment_url;
      }
      throw new Error(response.data.message);
    } catch (error) {
      console.error('Error creating payment:', error);
      throw error;
    }
  },

  /**
   * Redirect user to VNPay payment page
   * @param {string} bookingId
   */
  async redirectToVNPay(bookingId) {
    try {
      const paymentUrl = await this.createVNPayPayment(bookingId);
      window.location.href = paymentUrl;
    } catch (error) {
      console.error('Redirect failed:', error);
      alert('Failed to create payment. Please try again.');
    }
  }
};
```

React component example:

```javascript
// src/pages/CheckoutPage.jsx
import { paymentService } from '../services/paymentService';

export default function CheckoutPage() {
  const handleVNPayPayment = async (bookingId) => {
    try {
      await paymentService.redirectToVNPay(bookingId);
    } catch (error) {
      console.error('Payment error:', error);
    }
  };

  return (
    <div>
      <h2>Complete Your Booking</h2>
      <button onClick={() => handleVNPayPayment(bookingId)}>
        Pay with VNPay
      </button>
    </div>
  );
}
```

---

## Step 6: Important Configuration

### Add to `.env`:
```env
VNPAY_TMN_CODE=JVNWOIL0
VNPAY_HASH_SECRET=UKQ5BZ0MYX20ODFTZ8JGFE7F4DO3WGDE
VNPAY_PAYMENT_URL=https://sandbox.vnpayment.vn/paymentv2/vpcpay.html
VNPAY_API_URL=https://sandbox.vnpayment.vn/merchant_webapi/merchant_transaction
```

### Configure IPN Callback URL in VNPay Dashboard:

⚠️ **CRITICAL:** VNPay needs a public HTTPS URL to send IPN callbacks.

**For local development (use ngrok):**
```bash
# Terminal 1: Run your FastAPI backend
uvicorn main:app --reload --port 8000

# Terminal 2: Create public HTTPS tunnel
ngrok http 8000

# You'll get a URL like: https://xxxx-1-23-456-78-90.ngrok.io
# Configure IPN URL in VNPay dashboard as:
# https://xxxx-1-23-456-78-90.ngrok.io/api/payments/vnpay/ipn
```

**For production:**
- Use your actual domain: `https://yourdomain.com/api/payments/vnpay/ipn`
- Configure this in VNPay merchant dashboard

---

## Step 7: Test Payment

### Test Cards (Sandbox):

```
Bank: NCB (Ngan Hang Ngoai Thuong Viet Nam)
Card: 9704198526191432198
Cardholder: NGUYEN VAN A
OTP: 123456
```

### Test Flow:

1. Create a booking
2. Click "Pay with VNPay"
3. Fill payment form with test card
4. Enter OTP: 123456
5. You'll be redirected to return URL
6. Check booking status — should be "confirmed"

---

## Key Points to Remember

1. **Amount format:** VNPay requires `amount * 100` (e.g., 500,000 VND = 50000000)
2. **Signature:** All requests/responses must include `vnp_SecureHash` (HMAC-SHA512)
3. **Parameter order:** Must be sorted alphabetically before checksumming
4. **IPN callback:** Can be called multiple times (make it idempotent)
5. **Return vs IPN:** Return URL is for user redirect; IPN is server-to-server
6. **Public URL:** IPN callback must be accessible from the internet (HTTPS)
7. **Testing:** Use sandbox credentials until you're ready for live (requires account activation)

---

## Response Codes

| Code | Meaning | Action |
|------|---------|--------|
| 00 | Successful | Update booking to "confirmed" |
| 01 | User cancelled | Update booking to "cancelled" |
| 02 | Payment failed | Retry or contact support |
| 97 | Invalid checksum | Security error — log and ignore |

---

## Troubleshooting

### Payment URL doesn't load
- Check `VNPAY_PAYMENT_URL` is correct
- Verify `vnp_Amount` is > 0 and formatted correctly
- Ensure `vnp_ReturnUrl` is HTTPS and accessible

### IPN callback not received
- Configure IPN URL in VNPay merchant dashboard
- Use ngrok/public URL for local testing
- Check your backend logs for incoming requests
- Verify firewall/security groups allow incoming connections

### Checksum mismatch
- Verify `VNPAY_HASH_SECRET` matches email
- Ensure parameters are sorted alphabetically
- Check amount is formatted as `amount * 100`

### Payment shows "pending" instead of "success"
- Check IPN callback endpoint is correctly configured
- Verify response code "00" handling in code
- Check database transaction for Payment record

