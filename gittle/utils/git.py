# Python imports
import os
from StringIO import StringIO

# Dulwich imports
from dulwich import patch
from dulwich.objects import Blob

# Funky imports
from funky import first, true_only, rest, negate

# Mimer imports
from mimer import is_readable


def _is_readable_info(info):
    path, mode, sha = info
    return path is None or is_readable(path)


def is_readable_change(change):
    return all(
        map(_is_readable_info, change)
    )

is_unreadable_change = negate(is_readable_change)


def dummy_diff(*args, **kwargs):
    return ''


def commit_name_email(commit_author):
    try:
        name, email = commit_author.rsplit(' ', 1)
        # Extract the X from : "<X>"
        email = email[1:-1]
    except:
        name = commit_author
        email = ''
    return name, email


def contributor_from_raw(raw_author):
    name, email = commit_name_email(raw_author)
    return {
        'name': name,
        'email': email,
        'raw': raw_author
    }


def commit_info(commit):
    author = contributor_from_raw(commit.author)
    committer = contributor_from_raw(commit.committer)

    message_lines = commit.message.splitlines()
    summary = first(message_lines, '')
    description = '\n'.join(
        true_only(
            rest(
                message_lines
            )
        )
    )

    return {
        'author': author,
        'committer': committer,
        'sha': commit.sha().hexdigest(),
        'time': commit.commit_time,
        'timezone': commit.commit_timezone,
        'message': commit.message,
        'summary': summary,
        'description': description,
    }


def object_diff(*args, **kwargs):
    """A more convenient wrapper around Dulwich's patching
    """
    fd = StringIO()
    patch.write_object_diff(fd, *args, **kwargs)
    return fd.getvalue()


def blob_diff(object_store, *args, **kwargs):
    fd = StringIO()
    patch.write_blob_diff(fd, *args, **kwargs)
    return fd.getvalue()


def changes_to_pairs(changes):
    return [
        ((oldpath, oldmode, oldsha), (newpath, newmode, newsha),)
        for (oldpath, newpath), (oldmode, newmode), (oldsha, newsha) in changes
    ]


def _diff_pairs(object_store, pairs, diff_func, diff_type='text'):
    return [
        {
            'diff': diff_func(object_store, old, new),
            'new': change_to_dict(new),
            'old': change_to_dict(old),
            'type': diff_type
        }
        for old, new in pairs
    ]


def diff_changes(object_store, changes, diff_func=object_diff, filter_binary=True):
    """Return a dict of diffs for the changes
    """
    pairs = changes_to_pairs(changes)
    readable_pairs = filter(is_readable_change, pairs)
    unreadable_pairs = filter(is_unreadable_change, pairs)

    return sum([
        _diff_pairs(object_store, readable_pairs, diff_func),
        _diff_pairs(object_store, unreadable_pairs, dummy_diff, 'binary')
    ], [])


def obj_blob(object_store, info):
    if not any(info):
        return info
    path, mode, sha = info
    return (path, mode, object_store[sha])


def path_blob(basepath, info):
    if not any(info):
        return info
    path, mode, sha = info
    return blob_from_path(basepath, path)


def changes_to_blobs(object_store, basepath, pairs):
    return [
        (obj_blob(object_store, old), path_blob(basepath, new),)
        for old, new in pairs
    ]


def change_to_dict(info):
    path, mode, sha_or_blob = info

    if sha_or_blob and not is_sha(sha_or_blob):
        sha = sha_or_blob.id
    else:
        sha = sha_or_blob

    return {
        'path': path,
        'mode': mode,
        'sha': sha,
    }


def diff_changes_paths(object_store, basepath, changes, filter_binary=True):
    """Does a diff assuming that the old blobs are in git and others are unstaged blobs
       in the working directory
    """
    pairs = changes_to_pairs(changes)
    readable_pairs = filter(is_readable_change, pairs)
    unreadable_pairs = filter(is_unreadable_change, pairs)

    blobs = changes_to_blobs(object_store, basepath, readable_pairs)

    return sum([
        _diff_pairs(object_store, blobs, blob_diff),
        _diff_pairs(object_store, unreadable_pairs, dummy_diff, 'binary')
    ], [])


def changes_tree_diff(object_store, old_tree, new_tree):
    return object_store.tree_changes(old_tree, new_tree)


def dict_tree_diff(object_store, old_tree, new_tree, filter_binary=True):
    """Returns a dictionary where the keys are the filenames and their respective
    values are their diffs
    """
    changes = changes_tree_diff(object_store, old_tree, new_tree)
    return diff_changes(object_store, changes, filter_binary=filter_binary)


def classic_tree_diff(object_store, old_tree, new_tree):
    """Does a classic diff and returns the output in a buffer
    """
    output = StringIO()

    # Write to output (our string)
    patch.write_tree_diff(
        output,
        object_store,
        old_tree,
        new_tree
    )

    return output.getvalue()


def prune_tree(tree, paths):
    """Return a tree with only entries matching the list of paths supplied
    """
    raise NotImplemented()


def is_sha(sha):
    return isinstance(sha, basestring) and len(sha) == 40


def blob_from_path(basepath, path):
    """Returns a tuple of (sha_id, mode, blob)
    """
    fullpath = os.path.join(basepath, path)
    with open(fullpath, 'rb') as working_file:
        blob = Blob()
        blob.data = working_file.read()
    return (path, os.stat(fullpath).st_mode, blob)
