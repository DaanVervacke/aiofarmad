Messaging
=========

The messaging service carries the conversations with a pharmacy and the
compose flow behind them.

Reading one page of conversations and one page of messages works through
``async_get_conversations`` and ``async_get_conversation_messages``. The
pharmacy must have a patient file with messaging activated, otherwise both
raise :class:`aiofarmad.FarmadAuthorizationError`.

Composing works on one draft per account and pharmacy, which the app models
the same way: fetch the draft, create it when the answer is ``None``, update
the text, attach files, and send.

.. code-block:: python

    from pathlib import Path

    draft = await client.async_get_message_draft("343602")
    if draft is None:
        draft = await client.async_save_message_draft("343602", "hello")
    if draft is None:
        msg = "the pharmacy returned no draft"
        raise RuntimeError(msg)
    await client.async_update_message_draft("343602", draft.id, "hello pharmacy")
    await client.async_upload_message_attachment(
        "343602", draft.id, "note.pdf", Path("note.pdf").read_bytes()
    )
    await client.async_send_message_draft("343602", draft.id)

Sending consumes the draft: the next draft read answers ``None`` until a new
one is saved. ``async_upload_message_attachment`` returns the attachment id
and accepts pdf attachments only. The service answers any other content
type with a 500, raised as :class:`aiofarmad.FarmadCommunicationError`, so
the content type parameter defaults to ``application/pdf``. ``async_delete_message_attachment`` removes one
attachment by its id without the draft id in the path, and
``async_mark_message_as_read`` marks one message as read by the receiver.
