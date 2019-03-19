from astropy.io import fits
from astropy.table import Table
import scipy.linalg


class BaseCovariance:
    _covariance_classes = {}

    def __init_subclass__(cls, cov_type):
        cls._covariance_classes[cov_type] = cls
        cls.cov_type = cov_type

    @classmethod
    def from_fits(cls, hdu):
        subclass_name = hdu.header['saccclss']
        subclass = self._covariance_classes[subcls]
        return subclass.from_fits(hdu)

    @classmethod
    def make(cls, cov, n):
        if isinstance(cov,list):
            s = 0
            for block in cov:
                block = np.atleast_2d(block)
                if (block.ndim!=2) or (block.shape[0]!=block.shape[1]):
                    raise ValueError(f"Covariance block has wrong size or shape {block.shape}")
                s += block.shape[0]
            if s != n:
                raise ValueError(f"Covariance blocks do not have the right overall size ({s}x{s}, expected {n}x{n})")
            return BlockDiagonalCovariance(cov)
        else:
            cov = np.atleast_2d(cov)
            if (cov.ndim!=2) or (cov.shape[0]!=cov.shape[1]) or (cov.shape[0]!=n):
                raise ValueError(f"Covariance has wrong size or shape {cov.shape}, expected ({n}x{n})")
            return FullCovariance(cov)


class FullCovariance(BaseCovariance, cov_type='full'):
    def __init__(self, covmat):
        self.covmat = np.atleast_2d(covmat)

    def to_fits(self):
        hdu=fits.ImageHDU(self.covmat)
        hdu.name = 'covariance'
        hdu.header['sacctype'] = 'cov'
        hdu.header['saccclss'] = self.cov_type
        hdu.header['size'] = self.covmat.shape[0]
        return hdu

    def masked(self, mask):
        C = self.covmat[mask][:,mask]
        return self.__class__(C)

    @classmethod
    def from_fits(cls, hdu):
        C = hdu.data
        return cls(C)

    def get_block(self, indices):
        return self.covmat[indices][:,indices]

    def to_dict(self):
        return {"type":self.cov_type, "cov":self.covmat}

    @classmethod
    def from_dict(cls, d):
        return cls(d['covmat'])

class BlockDiagonalCovariance(BaseCovariance, cov_type='block'):
    def __init__(self, blocks):
        self.blocks = [np.atleast_2d(B) for B in blocks]
        self.block_sizes = [len(B) for B in self.blocks]
        self.total_size = sum(self.block_sizes)

    def to_fits(self):
        hdu=fits.ImageHDU(np.concatenate([b.flatten() for b in self.blocks]))
        hdu.name = 'covariance'
        hdu.header['sacctype'] = 'cov'
        hdu.header['saccclss'] = self.cov_type
        hdu.header['size'] = self.covmat.shape[0]
        hdu.header['blocks'] = len(self.block)
        for i,s in enumerate(self.block_sizes):
            hdu.header[f'size_{i}'] = s
        return hdu

    @classmethod
    def from_fits(cls, hdu):
        n = hdu.header['blocks']
        block_sizes = [hdu.header[f'size_{i}'] for i in range(n)]
        data_sizes = np.array(block_sizes)**2
        s = 0
        blocks = []
        for b in block_sizes:
            B = hdu.data[s:s+b**2].reshape((b,b))
            s += b**2
            blocks.append(B)
        return cls(blocks)


    def get_block(self, indices):
        n = len(indices)
        C = np.zeros((n,n))
        s = 0
        sub_blocks = []
        for b,sz in zip(self.blocks, self.block_sizes):
            e = s + sz
            m = indices[(indices>=s)&(indices<e)]
            sub_blocks.append(block[m][:,m])
            s += sz
        return scipy.linalg.block_diag(sub_blocks)
        


    def masked(self, mask):
        if mask.dtype == bool:
            breaks = np.cumsum(self.block_sizes)[:-1]
            block_masks = np.split(mask, breaks)
            blocks = [self.blocks[m][:,m] for m in block_masks]
            return self.__class__(blocks)
        elif (np.diff(mask)>0).all():
            s = 0
            sub_blocks = []
            for b,sz in zip(self.blocks, self.block_sizes):
                e = s + sz
                m = mask[(mask>=s)&(mask<e)]
                sub_blocks.append(block[m][:,m])
                s += sz
            return self.__class__(sub_blocks)
        else:
            C = scipy.linalg.block_diag(self.blocks)
            C = C[mask][:,mask]
            return FullCovariance(C)


    def to_dict(self):
        return {"type":self.cov_type, "blocks":self.blocks}

    @classmethod
    def from_dict(cls, d):
        return cls(d['blocks'])


class DiagonalCovariance(BaseCovariance, cov_type='diagonal')
    def __init__(self, diag):
        self.diag = np.atleast_1d(diag)
        self.size = len(diag)

    def to_fits(self):
        table = Table(names=['variance'], data=self.diag)
        hdu=fits.table_to_hdu(table)
        hdu.name = 'covariance'
        hdu.header['sacctype'] = 'cov'
        hdu.header['saccclss'] = self.cov_type
        return hdu

    def masked(self, mask):
        D = self.diag[mask]
        return self.__class__(D)

    @classmethod
    def from_fits(cls, hdu):
        D = hdu.data['variance']
        return cls(D)

    def get_block(self, indices):
        return np.diagonal(self.diag[indices])


    def to_dict(self):
        return {"type":self.cov_type, "blocks":self.diag}

    @classmethod
    def from_dict(cls, d):
        return cls(d['diag'])
