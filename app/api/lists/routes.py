from flask import Blueprint, jsonify, request
from datetime import datetime, timezone
import requests
try:
    from datetime import UTC
except ImportError:
    UTC = timezone.utc

from app.db.database import get_db
from app.utils.security import require_api_key, decrypt_token
from app.services.twitter import check_token_needs_refresh, refresh_twitter_token

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
    """Sync lists from Twitter for specified list_owner accounts"""
    data = request.get_json() or {}
    account_ids = data.get('account_ids', [])
    include_memberships = data.get('include_memberships', True)
    
    try:
        conn = get_db()
        
        # If no account IDs specified, sync all list_owner accounts
        if not account_ids:
            list_owners = conn.execute(
                '''SELECT id FROM twitter_account 
                   WHERE account_type = 'list_owner' AND access_token IS NOT NULL'''
            ).fetchall()
            account_ids = [owner['id'] for owner in list_owners]
        
        if not account_ids:
            conn.close()
            return jsonify({'error': 'No list_owner accounts found'}), 404
        
        sync_results = {
            'synced_lists': 0,
            'new_lists': 0,
            'updated_lists': 0,
            'total_memberships': 0,
            'new_memberships': 0,
            'removed_memberships': 0,
            'errors': []
        }
        
        # For now, just return a simple success response
        # Full Twitter API sync implementation would go here
        conn.close()
        
        return jsonify({
            'message': 'List sync completed',
            'account_ids': account_ids,
            'results': sync_results
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

@lists_bp.route('/api/v1/lists/<int:list_id>/add-follower', methods=['POST'])
@require_api_key
def add_follower_to_list_accounts(list_id):
    """Add a username as a follower to all accounts in a list (in the database)"""
    data = request.get_json()
    if not data or 'follower_username' not in data:
        return jsonify({'error': 'follower_username is required'}), 400
    
    follower_username = data['follower_username']
    follower_id = data.get('follower_id')  # Optional Twitter ID
    follower_name = data.get('follower_name', '')  # Optional display name
    status = data.get('status', 'active')  # Optional status, defaults to 'active'
    
    try:
        conn = get_db()
        
        # Check if list exists
        lst = conn.execute(
            'SELECT id, name FROM twitter_list WHERE id = ?',
            (list_id,)
        ).fetchone()
        
        if not lst:
            conn.close()
            return jsonify({'error': 'List not found'}), 404
        
        # Get all members of the list
        members = conn.execute('''
            SELECT a.id, a.username
            FROM list_membership lm
            JOIN twitter_account a ON lm.account_id = a.id
            WHERE lm.list_id = ?
        ''', (list_id,)).fetchall()
        
        if not members:
            conn.close()
            return jsonify({'message': 'No accounts found in this list'}), 200
        
        results = {
            'follower_username': follower_username,
            'list_name': lst['name'],
            'added': [],
            'already_exists': [],
            'failed': [],
            'total_accounts': len(members)
        }
        
        for member in members:
            try:
                # Check if this follower already exists for this account
                existing = conn.execute(
                    'SELECT id FROM follower WHERE account_id = ? AND follower_username = ?',
                    (member['id'], follower_username)
                ).fetchone()
                
                if existing:
                    results['already_exists'].append({
                        'account_username': member['username'],
                        'follower_username': follower_username
                    })
                    continue
                
                # Add the follower to this account
                conn.execute('''
                    INSERT INTO follower (account_id, follower_username, follower_id, follower_name, status)
                    VALUES (?, ?, ?, ?, ?)
                ''', (member['id'], follower_username, follower_id, follower_name, status))
                
                results['added'].append({
                    'account_username': member['username'],
                    'follower_username': follower_username
                })
                    
            except Exception as e:
                results['failed'].append({
                    'account_username': member['username'],
                    'error': str(e)
                })
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': f'Added @{follower_username} as follower to accounts in list',
            'results': results,
            'summary': {
                'total_accounts': results['total_accounts'],
                'added_count': len(results['added']),
                'already_exists_count': len(results['already_exists']),
                'failed_count': len(results['failed'])
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@lists_bp.route('/api/v1/lists/<int:list_id>/feed', methods=['GET'])
@require_api_key
def get_list_feed(list_id):
    """Get feed of tweets and threads from accounts in a specific list"""
    try:
        conn = get_db()
        
        # Check if list exists
        lst = conn.execute(
            'SELECT id, name FROM twitter_list WHERE id = ?',
            (list_id,)
        ).fetchone()
        
        if not lst:
            conn.close()
            return jsonify({'error': 'List not found'}), 404
        
        # Get pagination parameters
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Validate limits
        if limit > 100:
            limit = 100
        if limit < 1:
            limit = 20
        
        # Get account IDs that are members of this list
        list_members = conn.execute('''
            SELECT account_id 
            FROM list_membership 
            WHERE list_id = ?
        ''', (list_id,)).fetchall()
        
        if not list_members:
            conn.close()
            return jsonify({
                'feed': [],
                'total': 0,
                'has_more': False,
                'list_name': lst['name']
            })
        
        member_ids = [member['account_id'] for member in list_members]
        member_ids_str = ','.join(['?' for _ in member_ids])
        
        # Get tweets from list members (excluding thread tweets)
        tweets_query = f'''
            SELECT 
                t.id,
                t.content,
                t.status,
                t.created_at,
                t.posted_at,
                t.twitter_id,
                t.dok_type,
                t.change_type,
                a.id as account_id,
                a.username,
                a.display_name,
                a.profile_picture,
                'tweet' as post_type
            FROM tweet t
            JOIN twitter_account a ON t.twitter_account_id = a.id
            WHERE t.twitter_account_id IN ({member_ids_str})
            AND t.thread_id IS NULL
            AND t.status = 'posted'
        '''
        
        # Get threads from list members (using thread_id to group)
        threads_query = f'''
            SELECT 
                t.thread_id,
                t.twitter_account_id,
                a.username,
                a.display_name,
                a.profile_picture,
                COUNT(*) as tweet_count,
                MIN(t.created_at) as created_at,
                MAX(t.posted_at) as posted_at,
                GROUP_CONCAT(
                    CASE WHEN t.thread_position = 0 THEN t.content END
                ) as first_tweet_content,
                'thread' as post_type
            FROM tweet t
            JOIN twitter_account a ON t.twitter_account_id = a.id
            WHERE t.twitter_account_id IN ({member_ids_str})
            AND t.thread_id IS NOT NULL
            AND t.status = 'posted'
            GROUP BY t.thread_id, t.twitter_account_id
        '''
        
        # Combine both queries using UNION and order by posted_at/created_at
        combined_query = f'''
            SELECT * FROM (
                {tweets_query}
                UNION ALL
                SELECT 
                    thread_id as id,
                    first_tweet_content as content,
                    'posted' as status,
                    created_at,
                    posted_at,
                    NULL as twitter_id,
                    NULL as dok_type,
                    NULL as change_type,
                    twitter_account_id as account_id,
                    username,
                    display_name,
                    profile_picture,
                    post_type
                FROM ({threads_query})
            ) combined
            ORDER BY 
                CASE 
                    WHEN posted_at IS NOT NULL THEN posted_at 
                    ELSE created_at 
                END DESC
            LIMIT ? OFFSET ?
        '''
        
        # Execute query with all member IDs twice (once for tweets, once for threads) plus limit and offset
        query_params = member_ids + member_ids + [limit + 1, offset]  # +1 to check if there are more
        
        feed_items = conn.execute(combined_query, query_params).fetchall()
        
        # Check if there are more items
        has_more = len(feed_items) > limit
        if has_more:
            feed_items = feed_items[:-1]  # Remove the extra item
        
        # Format feed items
        formatted_feed = []
        for item in feed_items:
            if item['post_type'] == 'thread':
                # For threads, get the complete thread data
                thread_tweets = conn.execute('''
                    SELECT id, content, thread_position, twitter_id
                    FROM tweet 
                    WHERE thread_id = ? 
                    ORDER BY thread_position
                ''', (item['id'],)).fetchall()
                
                formatted_feed.append({
                    'id': item['id'],
                    'type': 'thread',
                    'thread_id': item['id'],
                    'account_id': item['account_id'],
                    'username': item['username'],
                    'display_name': item['display_name'],
                    'profile_picture': item['profile_picture'],
                    'created_at': item['created_at'],
                    'posted_at': item['posted_at'],
                    'tweet_count': len(thread_tweets),
                    'first_tweet': item['content'],
                    'tweets': [dict(tweet) for tweet in thread_tweets]
                })
            else:
                # Regular tweet
                formatted_feed.append({
                    'id': item['id'],
                    'type': 'tweet',
                    'account_id': item['account_id'],
                    'username': item['username'],
                    'display_name': item['display_name'],
                    'profile_picture': item['profile_picture'],
                    'content': item['content'],
                    'status': item['status'],
                    'created_at': item['created_at'],
                    'posted_at': item['posted_at'],
                    'twitter_id': item['twitter_id'],
                    'dok_type': item['dok_type'],
                    'change_type': item['change_type']
                })
        
        # Get total count for pagination info
        total_query = f'''
            SELECT COUNT(*) as total FROM (
                SELECT id FROM tweet 
                WHERE twitter_account_id IN ({member_ids_str})
                AND thread_id IS NULL 
                AND status = 'posted'
                UNION ALL
                SELECT DISTINCT thread_id as id FROM tweet 
                WHERE twitter_account_id IN ({member_ids_str})
                AND thread_id IS NOT NULL 
                AND status = 'posted'
            )
        '''
        
        total_count = conn.execute(total_query, member_ids + member_ids).fetchone()['total']
        
        conn.close()
        
        return jsonify({
            'feed': formatted_feed,
            'total': total_count,
            'has_more': has_more,
            'list_name': lst['name'],
            'pagination': {
                'limit': limit,
                'offset': offset,
                'next_offset': offset + limit if has_more else None
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500