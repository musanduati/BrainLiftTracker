from flask import Blueprint, jsonify, request
from datetime import datetime, timezone
import requests
try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc

from app.db.database import get_db
from app.utils.security import require_api_key, decrypt_token

lists_bp = Blueprint('lists', __name__)

@lists_bp.route('/api/v1/lists', methods=['POST'])
@require_api_key
def create_list():
    """Create a new Twitter list"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Required fields
    if 'name' not in data:
        return jsonify({'error': 'name is required'}), 400
    if 'owner_account_id' not in data:
        return jsonify({'error': 'owner_account_id is required'}), 400
    
    name = data['name']
    description = data.get('description', '')
    mode = data.get('mode', 'private')
    owner_account_id = data['owner_account_id']
    
    if mode not in ['private', 'public']:
        return jsonify({'error': 'mode must be "private" or "public"'}), 400
    
    try:
        conn = get_db()
        
        # Check if owner account exists and is a list_owner
        owner = conn.execute(
            'SELECT id, username, account_type, access_token FROM twitter_account WHERE id = ?',
            (owner_account_id,)
        ).fetchone()
        
        if not owner:
            conn.close()
            return jsonify({'error': 'Owner account not found'}), 404
        
        if owner['account_type'] != 'list_owner':
            conn.close()
            return jsonify({'error': 'Account must be of type "list_owner" to create lists'}), 400
        
        # Create list on Twitter
        access_token = decrypt_token(owner['access_token'])
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        list_data = {
            'name': name,
            'description': description,
            'private': mode == 'private'
        }
        
        response = requests.post(
            'https://api.twitter.com/2/lists',
            headers=headers,
            json=list_data
        )
        
        if response.status_code != 201:
            conn.close()
            return jsonify({
                'error': 'Failed to create list on Twitter',
                'details': response.json()
            }), response.status_code
        
        twitter_list = response.json()['data']
        list_id = twitter_list['id']
        
        # Save to database
        cursor = conn.execute(
            '''INSERT INTO twitter_list (list_id, name, description, mode, owner_account_id) 
               VALUES (?, ?, ?, ?, ?)''',
            (list_id, name, description, mode, owner_account_id)
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'List created successfully',
            'list': {
                'id': cursor.lastrowid,
                'list_id': list_id,
                'name': name,
                'description': description,
                'mode': mode,
                'owner_account_id': owner_account_id,
                'owner_username': owner['username']
            }
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@lists_bp.route('/api/v1/lists', methods=['GET'])
@require_api_key
def get_lists():
    """Get all lists"""
    owner_account_id = request.args.get('owner_account_id')
    include_external = request.args.get('include_external', 'false').lower() == 'true'
    
    try:
        conn = get_db()
        
        if owner_account_id:
            cursor = conn.execute('''
                SELECT l.*, a.username as owner_username 
                FROM twitter_list l
                JOIN twitter_account a ON l.owner_account_id = a.id
                WHERE l.owner_account_id = ?
                ORDER BY l.created_at DESC
            ''', (owner_account_id,))
        else:
            cursor = conn.execute('''
                SELECT l.*, a.username as owner_username 
                FROM twitter_list l
                JOIN twitter_account a ON l.owner_account_id = a.id
                ORDER BY l.created_at DESC
            ''')
        
        lists = cursor.fetchall()
        
        # Get member counts
        result = []
        for lst in lists:
            member_count = conn.execute(
                'SELECT COUNT(*) as count FROM list_membership WHERE list_id = ?',
                (lst['id'],)
            ).fetchone()['count']
            
            # Check for null values in new columns (for backwards compatibility)
            source = lst['source'] if 'source' in lst.keys() else 'created'
            is_managed = lst['is_managed'] if 'is_managed' in lst.keys() else 1
            last_synced_at = lst['last_synced_at'] if 'last_synced_at' in lst.keys() else None
            external_owner_username = lst['external_owner_username'] if 'external_owner_username' in lst.keys() else None
            
            result.append({
                'id': lst['id'],
                'list_id': lst['list_id'],
                'name': lst['name'],
                'description': lst['description'],
                'mode': lst['mode'],
                'owner_account_id': lst['owner_account_id'],
                'owner_username': lst['owner_username'],
                'member_count': member_count,
                'source': source,
                'is_managed': bool(is_managed),
                'last_synced_at': last_synced_at,
                'external_owner_username': external_owner_username,
                'created_at': lst['created_at'],
                'updated_at': lst['updated_at']
            })
        
        conn.close()
        
        return jsonify({
            'lists': result,
            'total': len(result)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@lists_bp.route('/api/v1/lists/<int:list_id>', methods=['GET'])
@require_api_key
def get_list(list_id):
    """Get specific list details"""
    try:
        conn = get_db()
        
        # Get list details
        lst = conn.execute('''
            SELECT l.*, a.username as owner_username 
            FROM twitter_list l
            JOIN twitter_account a ON l.owner_account_id = a.id
            WHERE l.id = ?
        ''', (list_id,)).fetchone()
        
        if not lst:
            conn.close()
            return jsonify({'error': 'List not found'}), 404
        
        # Get members
        members_cursor = conn.execute('''
            SELECT a.id, a.username, a.status, lm.added_at
            FROM list_membership lm
            JOIN twitter_account a ON lm.account_id = a.id
            WHERE lm.list_id = ?
            ORDER BY lm.added_at DESC
        ''', (list_id,))
        
        members = []
        for member in members_cursor:
            members.append({
                'id': member['id'],
                'username': member['username'],
                'status': member['status'],
                'added_at': member['added_at']
            })
        
        conn.close()
        
        return jsonify({
            'list': {
                'id': lst['id'],
                'list_id': lst['list_id'],
                'name': lst['name'],
                'description': lst['description'],
                'mode': lst['mode'],
                'owner_account_id': lst['owner_account_id'],
                'owner_username': lst['owner_username'],
                'created_at': lst['created_at'],
                'updated_at': lst['updated_at']
            },
            'members': members,
            'member_count': len(members)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@lists_bp.route('/api/v1/lists/<int:list_id>', methods=['PUT'])
@require_api_key
def update_list(list_id):
    """Update list details"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        conn = get_db()
        
        # Get list and owner details
        lst = conn.execute('''
            SELECT l.*, a.access_token 
            FROM twitter_list l
            JOIN twitter_account a ON l.owner_account_id = a.id
            WHERE l.id = ?
        ''', (list_id,)).fetchone()
        
        if not lst:
            conn.close()
            return jsonify({'error': 'List not found'}), 404
        
        # Update on Twitter
        access_token = decrypt_token(lst['access_token'])
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        update_data = {}
        if 'name' in data:
            update_data['name'] = data['name']
        if 'description' in data:
            update_data['description'] = data['description']
        
        if update_data:
            response = requests.put(
                f'https://api.twitter.com/2/lists/{lst["list_id"]}',
                headers=headers,
                json=update_data
            )
            
            if response.status_code != 200:
                conn.close()
                return jsonify({
                    'error': 'Failed to update list on Twitter',
                    'details': response.json()
                }), response.status_code
        
        # Update in database
        if 'name' in data:
            conn.execute(
                'UPDATE twitter_list SET name = ?, updated_at = ? WHERE id = ?',
                (data['name'], datetime.now(UTC).isoformat(), list_id)
            )
        if 'description' in data:
            conn.execute(
                'UPDATE twitter_list SET description = ?, updated_at = ? WHERE id = ?',
                (data['description'], datetime.now(UTC).isoformat(), list_id)
            )
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'List updated successfully',
            'list_id': list_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@lists_bp.route('/api/v1/lists/<int:list_id>', methods=['DELETE'])
@require_api_key
def delete_list(list_id):
    """Delete a list"""
    try:
        conn = get_db()
        
        # Get list details
        lst = conn.execute('''
            SELECT l.*, a.access_token 
            FROM twitter_list l
            JOIN twitter_account a ON l.owner_account_id = a.id
            WHERE l.id = ?
        ''', (list_id,)).fetchone()
        
        if not lst:
            conn.close()
            return jsonify({'error': 'List not found'}), 404
        
        # Delete from Twitter
        access_token = decrypt_token(lst['access_token'])
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        response = requests.delete(
            f'https://api.twitter.com/2/lists/{lst["list_id"]}',
            headers=headers
        )
        
        if response.status_code not in [200, 204]:
            conn.close()
            return jsonify({
                'error': 'Failed to delete list on Twitter',
                'details': response.text
            }), response.status_code
        
        # Delete from database (cascade will handle memberships)
        conn.execute('DELETE FROM twitter_list WHERE id = ?', (list_id,))
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'List deleted successfully',
            'list_id': list_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@lists_bp.route('/api/v1/lists/<int:list_id>/members', methods=['POST'])
@require_api_key
def add_list_members(list_id):
    """Add members to a list"""
    data = request.get_json()
    if not data or 'account_ids' not in data:
        return jsonify({'error': 'account_ids array is required'}), 400
    
    account_ids = data['account_ids']
    if not isinstance(account_ids, list):
        return jsonify({'error': 'account_ids must be an array'}), 400
    
    try:
        conn = get_db()
        
        # Get list and owner details
        lst = conn.execute('''
            SELECT l.*, a.access_token 
            FROM twitter_list l
            JOIN twitter_account a ON l.owner_account_id = a.id
            WHERE l.id = ?
        ''', (list_id,)).fetchone()
        
        if not lst:
            conn.close()
            return jsonify({'error': 'List not found'}), 404
        
        access_token = decrypt_token(lst['access_token'])
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        added_members = []
        failed_members = []
        
        for account_id in account_ids:
            # Get account details
            account = conn.execute(
                'SELECT id, username FROM twitter_account WHERE id = ?',
                (account_id,)
            ).fetchone()
            
            if not account:
                failed_members.append({
                    'account_id': account_id,
                    'error': 'Account not found'
                })
                continue
            
            # Check if already a member
            existing = conn.execute(
                'SELECT id FROM list_membership WHERE list_id = ? AND account_id = ?',
                (list_id, account_id)
            ).fetchone()
            
            if existing:
                failed_members.append({
                    'account_id': account_id,
                    'username': account['username'],
                    'error': 'Already a member'
                })
                continue
            
            # Get Twitter user ID
            user_response = requests.get(
                f'https://api.twitter.com/2/users/by/username/{account["username"]}',
                headers={'Authorization': f'Bearer {access_token}'}
            )
            
            if user_response.status_code != 200:
                failed_members.append({
                    'account_id': account_id,
                    'username': account['username'],
                    'error': 'Twitter user not found'
                })
                continue
            
            twitter_user_id = user_response.json()['data']['id']
            
            # Add to Twitter list
            add_response = requests.post(
                f'https://api.twitter.com/2/lists/{lst["list_id"]}/members',
                headers=headers,
                json={'user_id': twitter_user_id}
            )
            
            if add_response.status_code == 200:
                # Add to database
                conn.execute(
                    'INSERT INTO list_membership (list_id, account_id) VALUES (?, ?)',
                    (list_id, account_id)
                )
                added_members.append({
                    'account_id': account_id,
                    'username': account['username']
                })
            else:
                failed_members.append({
                    'account_id': account_id,
                    'username': account['username'],
                    'error': add_response.json().get('detail', 'Failed to add to Twitter list')
                })
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Added {len(added_members)} members to list',
            'added': added_members,
            'failed': failed_members
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@lists_bp.route('/api/v1/lists/<int:list_id>/members', methods=['GET'])
@require_api_key
def get_list_members(list_id):
    """Get members of a list"""
    try:
        conn = get_db()
        
        # Check if list exists
        lst = conn.execute(
            'SELECT * FROM twitter_list WHERE id = ?',
            (list_id,)
        ).fetchone()
        
        if not lst:
            conn.close()
            return jsonify({'error': 'List not found'}), 404
        
        # Get members
        members = conn.execute('''
            SELECT a.id, a.username, a.status, a.account_type, lm.added_at
            FROM list_membership lm
            JOIN twitter_account a ON lm.account_id = a.id
            WHERE lm.list_id = ?
            ORDER BY lm.added_at DESC
        ''', (list_id,)).fetchall()
        
        conn.close()
        
        return jsonify({
            'list_id': list_id,
            'members': [dict(member) for member in members],
            'member_count': len(members)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@lists_bp.route('/api/v1/lists/<int:list_id>/members/<int:account_id>', methods=['DELETE'])
@require_api_key
def remove_list_member(list_id, account_id):
    """Remove a member from a list"""
    try:
        conn = get_db()
        
        # Get list and owner details
        lst = conn.execute('''
            SELECT l.*, a.access_token 
            FROM twitter_list l
            JOIN twitter_account a ON l.owner_account_id = a.id
            WHERE l.id = ?
        ''', (list_id,)).fetchone()
        
        if not lst:
            conn.close()
            return jsonify({'error': 'List not found'}), 404
        
        # Get account details
        account = conn.execute(
            'SELECT username FROM twitter_account WHERE id = ?',
            (account_id,)
        ).fetchone()
        
        if not account:
            conn.close()
            return jsonify({'error': 'Account not found'}), 404
        
        # Check membership
        membership = conn.execute(
            'SELECT id FROM list_membership WHERE list_id = ? AND account_id = ?',
            (list_id, account_id)
        ).fetchone()
        
        if not membership:
            conn.close()
            return jsonify({'error': 'Account is not a member of this list'}), 404
        
        # Remove from Twitter
        access_token = decrypt_token(lst['access_token'])
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        # Get Twitter user ID
        user_response = requests.get(
            f'https://api.twitter.com/2/users/by/username/{account["username"]}',
            headers=headers
        )
        
        if user_response.status_code == 200:
            twitter_user_id = user_response.json()['data']['id']
            
            # Remove from Twitter list
            remove_response = requests.delete(
                f'https://api.twitter.com/2/lists/{lst["list_id"]}/members/{twitter_user_id}',
                headers=headers
            )
            
            if remove_response.status_code not in [200, 204]:
                conn.close()
                return jsonify({
                    'error': 'Failed to remove from Twitter list',
                    'details': remove_response.text
                }), remove_response.status_code
        
        # Remove from database
        conn.execute(
            'DELETE FROM list_membership WHERE list_id = ? AND account_id = ?',
            (list_id, account_id)
        )
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'Member removed from list successfully',
            'list_id': list_id,
            'account_id': account_id,
            'username': account['username']
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@lists_bp.route('/api/v1/lists/sync', methods=['POST'])
@require_api_key
def sync_twitter_lists():
    """Sync Twitter lists from external sources"""
    data = request.get_json() or {}
    owner_username = data.get('owner_username')
    
    if not owner_username:
        return jsonify({'error': 'owner_username is required'}), 400
    
    try:
        conn = get_db()
        
        # Get a list_owner account to use for API calls
        list_owner = conn.execute(
            "SELECT id, username, access_token FROM twitter_account WHERE account_type = 'list_owner' LIMIT 1"
        ).fetchone()
        
        if not list_owner:
            conn.close()
            return jsonify({'error': 'No list_owner account found'}), 404
        
        access_token = decrypt_token(list_owner['access_token'])
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        # Get user ID for the owner
        user_response = requests.get(
            f'https://api.twitter.com/2/users/by/username/{owner_username}',
            headers=headers
        )
        
        if user_response.status_code != 200:
            conn.close()
            return jsonify({'error': f'User {owner_username} not found on Twitter'}), 404
        
        user_id = user_response.json()['data']['id']
        
        # Get lists owned by this user
        lists_response = requests.get(
            f'https://api.twitter.com/2/users/{user_id}/owned_lists',
            headers=headers,
            params={'max_results': 100, 'list.fields': 'name,description,private'}
        )
        
        if lists_response.status_code != 200:
            conn.close()
            return jsonify({'error': 'Failed to fetch lists from Twitter'}), 500
        
        twitter_lists = lists_response.json().get('data', [])
        
        synced_lists = []
        for twitter_list in twitter_lists:
            # Check if list already exists
            existing = conn.execute(
                'SELECT id FROM twitter_list WHERE list_id = ?',
                (twitter_list['id'],)
            ).fetchone()
            
            if not existing:
                # Add new list
                cursor = conn.execute(
                    '''INSERT INTO twitter_list 
                       (list_id, name, description, mode, owner_account_id, source, external_owner_username, is_managed, last_synced_at) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        twitter_list['id'],
                        twitter_list['name'],
                        twitter_list.get('description', ''),
                        'private' if twitter_list.get('private', False) else 'public',
                        list_owner['id'],
                        'synced',
                        owner_username,
                        0,  # Not managed by us
                        datetime.now(UTC).isoformat()
                    )
                )
                synced_lists.append({
                    'id': cursor.lastrowid,
                    'list_id': twitter_list['id'],
                    'name': twitter_list['name'],
                    'action': 'added'
                })
            else:
                # Update existing list
                conn.execute(
                    '''UPDATE twitter_list 
                       SET name = ?, description = ?, last_synced_at = ?
                       WHERE list_id = ?''',
                    (
                        twitter_list['name'],
                        twitter_list.get('description', ''),
                        datetime.now(UTC).isoformat(),
                        twitter_list['id']
                    )
                )
                synced_lists.append({
                    'id': existing['id'],
                    'list_id': twitter_list['id'],
                    'name': twitter_list['name'],
                    'action': 'updated'
                })
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Synced {len(synced_lists)} lists from @{owner_username}',
            'lists': synced_lists
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@lists_bp.route('/api/v1/lists/sync/test', methods=['GET'])
@require_api_key
def test_sync_logic():
    """Test list sync logic"""
    return jsonify({
        'message': 'List sync test endpoint',
        'status': 'ready'
    })

@lists_bp.route('/api/v1/lists/move-members', methods=['POST'])
@require_api_key
def move_list_members():
    """Move members between lists"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    source_list_id = data.get('source_list_id')
    target_list_id = data.get('target_list_id')
    account_ids = data.get('account_ids', [])
    
    if not source_list_id or not target_list_id:
        return jsonify({'error': 'source_list_id and target_list_id are required'}), 400
    
    try:
        conn = get_db()
        
        # If no specific accounts, move all members
        if not account_ids:
            members = conn.execute(
                'SELECT account_id FROM list_membership WHERE list_id = ?',
                (source_list_id,)
            ).fetchall()
            account_ids = [m['account_id'] for m in members]
        
        moved = []
        failed = []
        
        for account_id in account_ids:
            try:
                # Check if already in target list
                existing = conn.execute(
                    'SELECT id FROM list_membership WHERE list_id = ? AND account_id = ?',
                    (target_list_id, account_id)
                ).fetchone()
                
                if not existing:
                    # Add to target list
                    conn.execute(
                        'INSERT INTO list_membership (list_id, account_id) VALUES (?, ?)',
                        (target_list_id, account_id)
                    )
                
                # Remove from source list
                conn.execute(
                    'DELETE FROM list_membership WHERE list_id = ? AND account_id = ?',
                    (source_list_id, account_id)
                )
                
                moved.append(account_id)
            except Exception as e:
                failed.append({'account_id': account_id, 'error': str(e)})
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Moved {len(moved)} members',
            'moved': moved,
            'failed': failed
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500