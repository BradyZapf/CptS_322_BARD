"""S1-02a Canvas plumbing (FR-02, FR-03). Spec: specs/features/S1-02a-canvas-plumbing/

How CanvasConnection turns Canvas errors into BARD's own, so the rest of the code never sees
canvasapi's exceptions.
"""

import pytest
import responses

from bard.canvas_connection import CanvasConnection, NotAvailable
from fakes import TOKEN, URL


@responses.activate
def test_forbidden_file_raises_not_available():
    responses.get(f"{URL}/api/v1/files/77", status=403,
                  json={"status": "unauthorized", "errors": [{"message": "user not authorized"}]})
    with pytest.raises(NotAvailable):
        CanvasConnection(URL, TOKEN).fetch_file(77)
