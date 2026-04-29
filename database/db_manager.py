from database.models import get_session, UserSettings, Portfolio

def get_user_settings(user_id):
    session = get_session()
    settings = session.query(UserSettings).filter_by(user_id=user_id).first()
    if not settings:
        settings = UserSettings(user_id=user_id)
        session.add(settings)
        session.commit()
    return settings

def update_user_settings(user_id, stock_id=None, data_length=None):
    session = get_session()
    settings = session.query(UserSettings).filter_by(user_id=user_id).first()
    if not settings:
        settings = UserSettings(user_id=user_id)
        session.add(settings)

    if stock_id:
        settings.stock_id = stock_id
    if data_length:
        settings.data_length = data_length

    session.commit()

def get_portfolio(user_id, slot=None):
    session = get_session()
    if slot:
        return session.query(Portfolio).filter_by(user_id=user_id, slot=slot).first()
    return session.query(Portfolio).filter_by(user_id=user_id).all()

def update_portfolio(user_id, slot, stock_id, entry_price, shares):
    session = get_session()
    item = session.query(Portfolio).filter_by(user_id=user_id, slot=slot).first()
    if not item:
        item = Portfolio(user_id=user_id, slot=slot)
        session.add(item)

    item.stock_id = stock_id
    item.entry_price = entry_price
    item.shares = shares
    session.commit()
